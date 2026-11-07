from collections import defaultdict

from app.normalization import FIELDS, stable

CAVEAT = "Recorded differences describe associations, not causes. Unrecorded conditions, setup and assay variability may affect reported yields. Same recorded conditions do not establish independent replicates."


def method(r):
    m = r.get("primary_measurement")
    return (
        (
            m["type"],
            m["unit"],
            m["kind"],
            m["analysis"].get("type"),
            m["original"].get("details"),
            m["original"].get("uses_authentic_standard"),
            m["original"].get("uses_internal_standard"),
        )
        if m
        and m["kind"] != "unspecified"
        and m["analysis"].get("type")
        and "conflicting_yield_measurements" not in r.get("diagnostics", [])
        else None
    )


def compare(a, b):
    strict = bool(a["group_id"] and a["group_id"] == b["group_id"])
    matches = []
    differences = []
    missing = []
    matrix = []
    for f in FIELDS:
        av, bv = a["conditions"][f], b["conditions"][f]
        status = (
            "unavailable"
            if av["value"] is None or bv["value"] is None
            else "match"
            if av["value"] == bv["value"]
            else "differ"
        )
        (
            missing
            if status == "unavailable"
            else matches
            if status == "match"
            else differences
        ).append(f)
        matrix.append(
            {"field": f, "a": av["label"], "b": bv["label"], "status": status}
        )
    compatible = method(a) is not None and method(a) == method(b)
    classification = (
        "not_comparable"
        if not strict
        else "incomplete"
        if missing or not compatible
        else "exact_recorded_conditions"
        if not differences
        else "single_recorded_factor"
        if len(differences) == 1
        else "multiple_recorded_factors"
    )
    delta = (
        b["yield_value"] - a["yield_value"]
        if strict
        and compatible
        and a["yield_value"] is not None
        and b["yield_value"] is not None
        else None
    )
    explanation = (
        "Both experiments have the same identified substrates and intended product. "
    )
    explanation += (
        ("Recorded differences: " + ", ".join(differences) + ". ")
        if differences
        else "No differences among known tracked conditions. "
    )
    if missing:
        explanation += "Unavailable factors: " + ", ".join(missing) + ". "
    if not compatible:
        explanation += "Yield measurement methods are missing or incompatible. "
    return {
        "strict_match": strict,
        "classification": classification,
        "delta_percentage_points": delta,
        "matches": matches,
        "differences": differences,
        "missing": missing,
        "matrix": matrix,
        "measurement_compatible": compatible,
        "explanation": explanation + CAVEAT,
        "caveat": CAVEAT,
        "a": a,
        "b": b,
    }


def insights(rows):
    valid = [r for r in rows if r["yield_value"] is not None]
    if not valid:
        return {
            "single_factor": [],
            "same_conditions": [],
            "extremes": None,
            "candidate_policy": "No valid primary yields",
        }
    complete = [
        r
        for r in valid
        if all(r["conditions"][f]["value"] is not None for f in FIELDS) and method(r)
    ]
    candidates = {}
    same = []
    for omit in [None, *FIELDS]:
        buckets = defaultdict(list)
        for r in complete:
            key = stable(
                [
                    method(r),
                    [(f, r["conditions"][f]["value"]) for f in FIELDS if f != omit],
                ]
            )
            buckets[key].append(r)
        for bucket in buckets.values():
            lo = min(bucket, key=lambda r: (r["yield_value"], r["id"]))
            hi = max(bucket, key=lambda r: (r["yield_value"], r["id"]))
            if lo["id"] == hi["id"]:
                continue
            pair = compare(lo, hi)
            item = {
                "reaction_ids": [lo["id"], hi["id"]],
                "delta": pair["delta_percentage_points"],
                "factor": omit,
                "classification": pair["classification"],
                "count": len(bucket),
            }
            if omit is None:
                same.append(item)
            elif pair["classification"] == "single_recorded_factor":
                candidates[tuple(item["reaction_ids"])] = item
    lo = min(valid, key=lambda r: (r["yield_value"], r["id"]))
    hi = max(valid, key=lambda r: (r["yield_value"], r["id"]))
    return {
        "single_factor": sorted(candidates.values(), key=lambda p: -(p["delta"] or 0))[
            :8
        ],
        "same_conditions": sorted(same, key=lambda p: -(p["delta"] or 0))[:5],
        "extremes": {
            "reaction_ids": [lo["id"], hi["id"]],
            "delta": compare(lo, hi)["delta_percentage_points"],
        },
        "candidate_policy": "Largest observed valid-yield contrast per leave-one-factor-out condition signature; not an exhaustive ranking of all pairs.",
    }
