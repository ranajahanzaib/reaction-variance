import csv
import io

import pytest
from app.ingestion import DB
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_not_imported(monkeypatch, tmp_path):
    monkeypatch.setenv("REACTION_DB", str(tmp_path / "absent.sqlite"))
    assert client.get("/api/health").json()["dataset_ready"] is False
    assert client.get("/api/groups").status_code == 503


@pytest.fixture
def gid():
    if not DB.exists():
        pytest.skip("Run make ingest for real-dataset integration tests")
    return client.get("/api/groups").json()["items"][0]["id"]


def test_metadata(gid):
    d = client.get("/api/dataset").json()
    assert d["audit"]["record_count"] == 50688
    assert len(d["sha256"]) == 64 and d["license"] == "CC-BY-SA-4.0"
    assert client.get("/api/groups?sort=invalid").status_code == 422
    assert client.get("/api/groups?offset=-1").status_code == 422


def test_pages_sort_filter(gid):
    path = f"/api/groups/{gid}/reactions"
    a = client.get(path + "?limit=2").json()
    b = client.get(path + "?limit=2&offset=2").json()
    assert len(a["items"]) == 2 and not {r["id"] for r in a["items"]} & {
        r["id"] for r in b["items"]
    }
    assert a["items"][0]["yield_value"] >= a["items"][1]["yield_value"]
    first = a["items"][0]
    filtered = client.get(
        path,
        params={"catalyst": first["conditions"]["catalyst"]["label"], "yield_min": 10},
    ).json()
    assert all(
        r["conditions"]["catalyst"]["value"] == first["conditions"]["catalyst"]["value"]
        and r["yield_value"] >= 10
        for r in filtered["items"]
    )
    assert client.get(path, params={"catalyst": "invented"}).status_code == 422
    assert client.get(path + "?yield_min=80&yield_max=20").status_code == 422
    assert client.get(path + "?yield_min=100&yield_max=100").json()["total"] >= 0
    assert client.get(path + "?offset=999999").json()["items"] == []


def test_retrieval_comparison(gid):
    rows = client.get(f"/api/groups/{gid}/reactions?limit=2").json()["items"]
    ids = ",".join(r["id"] for r in rows)
    result = client.get("/api/compare", params={"reaction_ids": ids})
    assert result.status_code == 200
    assert len(result.json()["matrix"]) == 10
    assert client.get("/api/reactions/" + rows[0]["id"]).json()["id"] == rows[0]["id"]
    assert client.get("/api/reactions/nonexistent").status_code == 404
    assert client.get("/api/groups/nonexistent").status_code == 404
    assert client.get("/api/compare?reaction_ids=missing,missing").status_code == 404
    assert client.get("/api/compare?reaction_ids=one").status_code == 422
    other = client.get("/api/groups").json()["items"][1]["id"]
    rid = client.get(f"/api/groups/{other}/reactions?limit=1").json()["items"][0]["id"]
    assert (
        client.get(
            "/api/compare", params={"reaction_ids": rows[0]["id"] + "," + rid}
        ).status_code
        == 422
    )
    export = client.get("/api/export", params={"reaction_ids": ids})
    parsed = list(csv.DictReader(io.StringIO(export.text)))
    assert len(parsed) == 2 and parsed[0]["license"].startswith("CC-BY-SA-4.0")
    assert parsed[0]["reaction_id"] == rows[0]["id"]
    assert client.get("/api/export").status_code == 422


def test_charts(gid):
    d = client.get(f"/api/groups/{gid}/distribution?dimension=base").json()
    assert sum(b["count"] for b in d["histogram"]) == d["usable"]
    assert sum(b["count"] for b in d["by_condition"]) == d["usable"]
    assert d["count"] >= d["usable"]
    r = client.get("/api/structure?smiles=CCO")
    assert r.status_code == 200 and "<svg" in r.text
    assert client.get("/api/structure?smiles=invalid").status_code == 422
