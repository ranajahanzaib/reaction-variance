"""Re-read the two example records from source using the supported ORD API.

Run from the repository root: PYTHONPATH=backend backend/.venv/bin/python scripts/verify-example.py
"""

import json

from app.comparison import compare
from app.ingestion import RAW, ROOT
from app.normalization import normalize
from google.protobuf.json_format import MessageToDict
from ord_schema import datasets

IDS = ["ord-2365576395864708ae020b624bece2bb", "ord-440750aca6d3422093ac4d79398fb3c3"]
source = datasets.load_dataset(str(RAW))
positions = {rid: i for i, rid in enumerate(source.iter_reaction_ids()) if rid in IDS}
rows = [
    normalize(
        MessageToDict(source.get_reaction(rid), preserving_proto_field_name=True),
        positions[rid],
    )
    for rid in IDS
]
result = compare(*rows)
assert result["classification"] == "single_recorded_factor"
assert result["differences"] == ["catalyst"]
assert abs(result["delta_percentage_points"] - 99.18171) < 1e-8
assert result["a"]["yield_value"] == 0
assert (
    result["b"]["primary_measurement"]["original"]["details"]
    == "assay yield from calibration curve"
)
(ROOT / "reports/verified-comparison.json").write_text(
    json.dumps(result, indent=2) + "\n"
)
print(
    f"Source-verified: {IDS[0]} vs {IDS[1]}; {result['delta_percentage_points']} percentage points; catalyst differs"
)
