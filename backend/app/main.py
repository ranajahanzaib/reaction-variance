import csv
import io
import json
import os
import sqlite3
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from app.comparison import compare, insights
from app.ingestion import DB, ROOT
from app.normalization import DATASET_ID, DOI, FIELDS
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from rdkit import Chem
from rdkit.Chem.Draw import rdMolDraw2D

app = FastAPI(title="ReactionVariance", version="0.1.0")


class Health(BaseModel):
    status: str
    dataset_ready: bool
    setup: str | None = None


class Record(BaseModel):
    id: str
    group_id: str | None
    dataset_id: str
    source_row: int
    substrates: list[dict[str, Any]]
    products: list[dict[str, Any]]
    yield_value: float | None
    primary_measurement: dict[str, Any] | None
    measurements: list[dict[str, Any]]
    conditions: dict[str, dict[str, Any]]
    diagnostics: list[str]
    source_identifiers: list[dict[str, Any]]
    setup: dict[str, Any] | None
    provenance: dict[str, Any]


class Group(BaseModel):
    id: str
    count: int
    usable: int
    minimum: float | None
    maximum: float | None
    median: float | None
    stddev: float | None
    spread: float | None
    substrates: list[dict[str, Any]]
    products: list[dict[str, Any]]
    dimensions: dict[str, list[str]]


class GroupPage(BaseModel):
    items: list[Group]
    total: int
    offset: int
    limit: int


class ReactionPage(BaseModel):
    items: list[Record]
    total: int
    offset: int
    limit: int


class Comparison(BaseModel):
    strict_match: bool
    classification: str
    delta_percentage_points: float | None
    matches: list[str]
    differences: list[str]
    missing: list[str]
    matrix: list[dict[str, str]]
    measurement_compatible: bool
    explanation: str
    caveat: str
    a: Record
    b: Record


class Dataset(BaseModel):
    dataset_id: str
    name: str
    description: str
    source_url: str
    doi: str
    sha256: str
    imported_at: str
    versions: dict[str, str]
    parser_version: str
    license: str
    audit: dict[str, Any]


class Insights(BaseModel):
    single_factor: list[dict[str, Any]]
    same_conditions: list[dict[str, Any]]
    extremes: dict[str, Any] | None
    candidate_policy: str


class Distribution(BaseModel):
    count: int
    usable: int
    median: float | None
    minimum: float | None
    maximum: float | None
    histogram: list[dict[str, Any]]
    by_condition: list[dict[str, Any]]
    dimension: str


@contextmanager
def db():
    path = Path(os.environ.get("REACTION_DB", str(DB)))
    if not path.exists():
        raise HTTPException(
            503, "Dataset not imported. Run make download and make ingest."
        )
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        yield con
    finally:
        con.close()


def get_record(con, rid):
    row = con.execute("SELECT payload FROM reactions WHERE id=?", (rid,)).fetchone()
    if not row:
        raise HTTPException(404, "Unknown ORD reaction ID")
    return json.loads(row[0])


def get_group(con, gid):
    row = con.execute("SELECT payload FROM groups WHERE id=?", (gid,)).fetchone()
    if not row:
        raise HTTPException(404, "Unknown substrate/product group")
    return json.loads(row[0])


@app.get("/api/health", response_model=Health)
def health():
    ready = Path(os.environ.get("REACTION_DB", str(DB))).exists()
    return {
        "status": "ok",
        "dataset_ready": ready,
        "setup": None if ready else "Run make download && make ingest",
    }


@app.get("/api/dataset", response_model=Dataset)
def dataset():
    with db() as con:
        return json.loads(con.execute("SELECT payload FROM dataset").fetchone()[0])


@app.get("/api/groups", response_model=GroupPage)
def groups(
    sort: Literal["count", "spread", "stddev", "usable"] = "spread",
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    with db() as con:
        total = con.execute("SELECT count(*) FROM groups WHERE count>1").fetchone()[0]
        rows = con.execute(
            f"SELECT payload FROM groups WHERE count>1 ORDER BY {sort} DESC,id LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return {
            "items": [json.loads(r[0]) for r in rows],
            "total": total,
            "offset": offset,
            "limit": limit,
        }


@app.get("/api/groups/{gid}", response_model=Group)
def group(gid: str):
    with db() as con:
        return get_group(con, gid)


FILTERS = ("catalyst", "ligand", "base", "solvent", "temperature", "duration")


def selection(
    gid,
    catalyst=None,
    ligand=None,
    base=None,
    solvent=None,
    temperature=None,
    duration=None,
    yield_min=None,
    yield_max=None,
):
    where = ["group_id=?"]
    args = [gid]
    values = locals().copy()
    if yield_min is not None and yield_max is not None and yield_min > yield_max:
        raise HTTPException(422, "yield_min must not exceed yield_max")
    for f in FILTERS:
        if values[f] is not None:
            where.append(f"{f}=?")
            args.append(values[f])
    if yield_min is not None:
        where.append("yield_value>=?")
        args.append(yield_min)
    if yield_max is not None:
        where.append("yield_value<=?")
        args.append(yield_max)
    return " AND ".join(where), args


def query_filters(
    catalyst: str | None = None,
    ligand: str | None = None,
    base: str | None = None,
    solvent: str | None = None,
    temperature: str | None = None,
    duration: str | None = None,
    yield_min: float | None = Query(None, ge=0, le=100),
    yield_max: float | None = Query(None, ge=0, le=100),
):
    return locals()


from fastapi import Depends


@app.get("/api/groups/{gid}/reactions", response_model=ReactionPage)
def reactions(
    gid: str,
    filters: Annotated[dict, Depends(query_filters)],
    sort: Literal[
        "yield_value",
        "catalyst",
        "ligand",
        "base",
        "solvent",
        "temperature",
        "duration",
    ] = "yield_value",
    direction: Literal["asc", "desc"] = "desc",
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    with db() as con:
        g = get_group(con, gid)
        for f in FILTERS:
            if filters[f] is not None and filters[f] not in g["dimensions"][f]:
                raise HTTPException(422, f"Unsupported {f} value for this group")
        where, args = selection(gid, **filters)
        total = con.execute(
            f"SELECT count(*) FROM reactions WHERE {where}", args
        ).fetchone()[0]
        order = (
            f'CAST(REPLACE({sort}, " °C", "") AS REAL)'
            if sort in ("temperature", "duration")
            else sort
        )
        rows = con.execute(
            f"SELECT payload FROM reactions WHERE {where} ORDER BY {sort} IS NULL,{order} {direction},id LIMIT ? OFFSET ?",
            (*args, limit, offset),
        )
        return {
            "items": [json.loads(r[0]) for r in rows],
            "total": total,
            "offset": offset,
            "limit": limit,
        }


@app.get("/api/reactions/{rid}", response_model=Record)
def reaction(rid: str):
    with db() as con:
        return get_record(con, rid)


@app.get("/api/compare", response_model=Comparison)
def comparison(reaction_ids: str):
    ids = reaction_ids.split(",")
    if len(ids) != 2:
        raise HTTPException(
            422, "Select exactly two ORD reaction IDs separated by a comma"
        )
    with db() as con:
        result = compare(*[get_record(con, i) for i in ids])
    if not result["strict_match"]:
        raise HTTPException(
            422,
            "Experiments do not have the same strictly identified substrates and intended product",
        )
    return result


@app.get("/api/groups/{gid}/insights", response_model=Insights)
def group_insights(gid: str):
    with db() as con:
        get_group(con, gid)
        return insights(
            [
                json.loads(r[0])
                for r in con.execute(
                    "SELECT payload FROM reactions WHERE group_id=?", (gid,)
                )
            ]
        )


@app.get("/api/groups/{gid}/distribution", response_model=Distribution)
def distribution(
    gid: str,
    filters: Annotated[dict, Depends(query_filters)],
    dimension: Literal[
        "catalyst", "ligand", "base", "solvent", "temperature", "duration"
    ] = "catalyst",
):
    import pandas as pd

    with db() as con:
        get_group(con, gid)
        where, args = selection(gid, **filters)
        rows = con.execute(
            f"SELECT yield_value,{dimension} FROM reactions WHERE {where}", args
        ).fetchall()
    valid = [(r[0], r[1]) for r in rows if r[0] is not None]
    ys = pd.Series([r[0] for r in valid], dtype=float)
    hist = [
        {
            "bin": f"{i}–{i + 10}",
            "count": sum(i <= y < (i + 10) or (i == 90 and y == 100) for y, _ in valid),
        }
        for i in range(0, 100, 10)
    ]
    cats = sorted({r[1] for r in valid})
    by = []
    for c in cats:
        values = pd.Series([y for y, label in valid if label == c], dtype=float)
        by.append(
            {
                "label": c,
                "count": len(values),
                "minimum": float(values.min()),
                "maximum": float(values.max()),
                "median": float(values.median()),
                "q1": float(values.quantile(0.25)),
                "q3": float(values.quantile(0.75)),
            }
        )
    return {
        "count": len(rows),
        "usable": len(valid),
        "median": float(ys.median()) if len(ys) else None,
        "minimum": float(ys.min()) if len(ys) else None,
        "maximum": float(ys.max()) if len(ys) else None,
        "histogram": hist,
        "by_condition": by,
        "dimension": dimension,
    }


@lru_cache(maxsize=256)
def draw(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise HTTPException(422, "Invalid molecular SMILES")
    drawer = rdMolDraw2D.MolDraw2DSVG(320, 160)
    drawer.DrawMolecule(mol)
    drawer.FinishDrawing()
    return drawer.GetDrawingText()


@app.get("/api/structure")
def structure(smiles: str = Query(min_length=1, max_length=2000)):
    return Response(
        draw(smiles),
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get("/api/export")
def export(
    filters: Annotated[dict, Depends(query_filters)],
    group_id: str | None = None,
    reaction_ids: str | None = None,
):
    classification = "not a pairwise comparison"
    with db() as con:
        if bool(group_id) == bool(reaction_ids):
            raise HTTPException(422, "Provide either group_id or reaction_ids")
        if group_id:
            get_group(con, group_id)
            where, args = selection(group_id, **filters)
            rs = [
                json.loads(r[0])
                for r in con.execute(
                    f"SELECT payload FROM reactions WHERE {where} ORDER BY id", args
                )
            ]
        else:
            result = comparison(reaction_ids)
            rs = [result["a"], result["b"]]
            classification = result["classification"]
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        [
            "dataset_id",
            "reaction_id",
            "source_row",
            "substrates_smiles",
            "product_smiles",
            "reported_yield_percent",
            "measurement_type",
            "measurement_original",
            "analysis",
            "classification",
            *FIELDS,
            "original_conditions",
            "publication",
            "attribution",
            "license",
        ]
    )
    for r in rs:
        m = r["primary_measurement"] or {}
        writer.writerow(
            [
                DATASET_ID,
                r["id"],
                r["source_row"],
                json.dumps(r["substrates"]),
                json.dumps(r["products"]),
                r["yield_value"] if r["yield_value"] is not None else "UNAVAILABLE",
                m.get("type", "UNAVAILABLE"),
                json.dumps(m.get("original")),
                json.dumps(m.get("analysis")),
                classification,
                *[r["conditions"][f]["label"] for f in FIELDS],
                json.dumps(r["conditions"]),
                DOI,
                "Open Reaction Database; source study authors; derived by ReactionVariance",
                "CC-BY-SA-4.0 https://creativecommons.org/licenses/by-sa/4.0/",
            ]
        )
    return Response(
        out.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="reactionvariance-{group_id or "comparison"}.csv"'
        },
    )


DIST = ROOT / "frontend/dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/")
    def index():
        return FileResponse(DIST / "index.html")
