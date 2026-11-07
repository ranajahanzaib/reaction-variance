"""Download, inspect, and atomically rebuild the local scientific database."""

import argparse
import hashlib
import json
import sqlite3
import urllib.request
from collections import Counter, defaultdict
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import pandas as pd
from app.normalization import DATASET_ID, DOI, FIELDS, SOURCE_URL, normalize, stable
from google.protobuf.json_format import MessageToDict
from ord_schema import datasets

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/source.parquet"
DB = ROOT / "data/processed/reactions.sqlite"


def records(path=RAW):
    source = datasets.load_dataset(str(path))
    for i, r in enumerate(source.reactions):
        yield normalize(MessageToDict(r, preserving_proto_field_name=True), i)


def audit(rows):
    counts = Counter(d for r in rows for d in r["diagnostics"])
    ids = Counter(r["id"] for r in rows)
    groups = Counter(r["group_id"] for r in rows if r["group_id"])
    return {
        "record_count": len(rows),
        "usable_identifiers": sum(not r["id"].startswith("missing-id") for r in rows),
        "strict_identity_records": sum(groups.values()),
        "comparable_groups": sum(n > 1 for n in groups.values()),
        "group_counts": dict(groups),
        "usable_yields": sum(r["yield_value"] is not None for r in rows),
        "zero_yields": sum(r["yield_value"] == 0 for r in rows),
        "duplicate_ids": sum(n - 1 for n in ids.values()),
        "duplicate_normalized_records": len(rows)
        - len(
            {stable([r["group_id"], r["conditions"], r["measurements"]]) for r in rows}
        ),
        "diagnostics": dict(counts),
        "coverage": {
            f: sum(r["conditions"][f]["value"] is not None for r in rows)
            for f in FIELDS
        },
        "condition_values": {
            f: sorted({r["conditions"][f]["label"] for r in rows}) for f in FIELDS
        },
        "measurement_types_all_products": dict(
            Counter(t for r in rows for t in r["source_summary"]["measurement_types"])
        ),
        "input_roles": dict(
            Counter(t for r in rows for t in r["source_summary"]["roles"])
        ),
        "substrate_identities": sorted(
            {stable(c) for r in rows for c in r["substrates"]}
        ),
        "intended_product_identities": sorted(
            {stable(c) for r in rows for c in r["products"]}
        ),
        "measurement_types": dict(
            Counter(m["type"] for r in rows for m in r["measurements"])
        ),
        "analysis_types": dict(
            Counter(
                m["analysis"].get("type", "unspecified")
                for r in rows
                for m in r["measurements"]
            )
        ),
        "yield_range_including_flagged": [
            min(m["value"] for r in rows for m in r["measurements"]),
            max(m["value"] for r in rows for m in r["measurements"]),
        ],
    }


def run(command):
    RAW.parent.mkdir(parents=True, exist_ok=True)
    if command == "download":
        if not RAW.exists():
            temp = RAW.with_suffix(".download")
            urllib.request.urlretrieve(SOURCE_URL, temp)
            temp.replace(RAW)
        print(f"{RAW}: {hashlib.sha256(RAW.read_bytes()).hexdigest()}")
        return
    if not RAW.exists():
        raise SystemExit("Run make download first.")
    source = datasets.load_dataset(str(RAW))
    if source.dataset_id != DATASET_ID:
        raise SystemExit(
            f"Unexpected dataset {source.dataset_id}; expected {DATASET_ID}"
        )
    print("Reading source with ord-schema DatasetView…", flush=True)
    rows = list(records())
    report = audit(rows)
    metadata = {
        "dataset_id": DATASET_ID,
        "name": source.name,
        "description": source.description,
        "source_url": SOURCE_URL,
        "doi": DOI,
        "sha256": hashlib.sha256(RAW.read_bytes()).hexdigest(),
        "imported_at": datetime.now(UTC).isoformat(),
        "versions": {
            p: version(p)
            for p in ("ord-schema", "protobuf", "rdkit", "pandas", "pyarrow")
        },
        "parser_version": "0.1.0",
        "license": "CC-BY-SA-4.0",
        "audit": report,
    }
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports/data-audit.json").write_text(json.dumps(metadata, indent=2))
    lines = [
        "# ORD source data audit",
        f"\nDataset: `{DATASET_ID}`",
        f"\nSHA-256: `{metadata['sha256']}`",
        f"\nImported UTC: {metadata['imported_at']}",
        "\n## Counts",
        *[f"- {k}: {v}" for k, v in report.items() if not isinstance(v, (dict, list))],
        "\n## Field coverage",
        *[f"- {f}: {n}/{len(rows)}" for f, n in report["coverage"].items()],
        "\n## Diagnostics",
        *[f"- {f}: {n}" for f, n in report["diagnostics"].items()],
        "\nSee `data-audit.json` for exact condition values, package versions and group counts. See `docs/methodology.md` for the extraction and comparison policy. Reported values outside 0–100 are retained in measurement provenance but excluded from summaries; no clipping. Duplicate normalized signatures are observations, not proof of independent replicates. Source records are retained once per source row.",
        "\nAttribution: Open Reaction Database and the authors of "
        + DOI
        + ". Derived data: CC-BY-SA-4.0.",
    ]
    (ROOT / "reports/data-audit.md").write_text("\n".join(lines) + "\n")
    if command == "inspect":
        print(json.dumps(report, indent=2))
        return
    DB.parent.mkdir(parents=True, exist_ok=True)
    temp = DB.with_suffix(".tmp")
    temp.unlink(missing_ok=True)
    con = sqlite3.connect(temp)
    con.executescript(
        """CREATE TABLE dataset (payload TEXT NOT NULL); CREATE TABLE reactions (id TEXT PRIMARY KEY, group_id TEXT, yield_value REAL, catalyst TEXT, ligand TEXT, base TEXT, solvent TEXT, temperature TEXT, duration TEXT, payload TEXT NOT NULL); CREATE TABLE groups (id TEXT PRIMARY KEY, count INTEGER, usable INTEGER, minimum REAL, maximum REAL, median REAL, stddev REAL, spread REAL, payload TEXT NOT NULL); CREATE TABLE diagnostics (reaction_id TEXT, category TEXT);"""
    )
    if report["duplicate_ids"]:
        raise ValueError(
            "Duplicate reaction IDs require review; refusing ambiguous import"
        )
    con.execute("INSERT INTO dataset VALUES (?)", (stable(metadata),))
    grouped = defaultdict(list)
    for r in rows:
        con.execute(
            "INSERT INTO reactions VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                r["id"],
                r["group_id"],
                r["yield_value"],
                *[
                    r["conditions"][f]["label"]
                    for f in (
                        "catalyst",
                        "ligand",
                        "base",
                        "solvent",
                        "temperature",
                        "duration",
                    )
                ],
                stable(r),
            ),
        )
        con.executemany(
            "INSERT INTO diagnostics VALUES (?,?)",
            [(r["id"], d) for d in r["diagnostics"]],
        )
        if r["group_id"]:
            grouped[r["group_id"]].append(r)
    for gid, rs in grouped.items():
        ys = pd.Series(
            [r["yield_value"] for r in rs if r["yield_value"] is not None], dtype=float
        )
        nums = (
            [
                float(ys.min()),
                float(ys.max()),
                float(ys.median()),
                float(ys.std(ddof=1)) if len(ys) > 1 else None,
                float(ys.max() - ys.min()),
            ]
            if len(ys)
            else [None] * 5
        )
        g = {
            "id": gid,
            "count": len(rs),
            "usable": len(ys),
            "minimum": nums[0],
            "maximum": nums[1],
            "median": nums[2],
            "stddev": nums[3],
            "spread": nums[4],
            "substrates": rs[0]["substrates"],
            "products": rs[0]["products"],
            "dimensions": {
                f: sorted({r["conditions"][f]["label"] for r in rs}) for f in FIELDS
            },
        }
        con.execute(
            "INSERT INTO groups VALUES (?,?,?,?,?,?,?,?,?)",
            (gid, len(rs), len(ys), *nums, stable(g)),
        )
    for f in (
        "group_id",
        "yield_value",
        "catalyst",
        "ligand",
        "base",
        "solvent",
        "temperature",
        "duration",
    ):
        con.execute(f"CREATE INDEX idx_{f} ON reactions ({f})")
    con.commit()
    con.close()
    temp.replace(DB)
    print(
        json.dumps(
            {k: v for k, v in report.items() if not isinstance(v, (dict, list))},
            indent=2,
        )
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["download", "inspect", "import", "rebuild"])
    run(p.parse_args().command)
