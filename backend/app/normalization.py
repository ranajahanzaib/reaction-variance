"""Conservative, dataset-specific ORD normalization. No chemical equivalence heuristics."""

import hashlib
import json
import math
from functools import lru_cache

from rdkit import Chem

DATASET_ID = "ord_dataset-805ad863feef48579d95d86a728035f4"
DOI = "https://doi.org/10.1021/jacs.6c05959"
SOURCE_URL = f"https://huggingface.co/datasets/open-reaction-database/ord-data/resolve/main/data/80/{DATASET_ID}.parquet"
FIELDS = (
    "substrate_amounts",
    "catalyst",
    "ligand",
    "base",
    "solvent",
    "temperature",
    "duration",
    "atmosphere",
    "stirring",
    "other",
)


def stable(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


@lru_cache(maxsize=4096)
def canonical(smiles):
    mol = Chem.MolFromSmiles(smiles)
    return Chem.MolToSmiles(mol, isomericSmiles=True) if mol else None


def compound(c):
    ids = c.get("identifiers", [])
    raw_smiles = [i["value"] for i in ids if i.get("type") == "SMILES"]
    structures = {canonical(v) for v in raw_smiles}
    issues = []
    if None in structures:
        issues.append("invalid_smiles")
    if not raw_smiles:
        issues.append("missing_smiles")
    if len(structures) > 1:
        issues.append("ambiguous_smiles")
    smi = next(iter(structures)) if len(structures) == 1 and not issues else None
    name = next(
        (i["value"] for i in ids if i.get("type") == "NAME"), smi or "Unidentified"
    )
    return {
        "smiles": smi,
        "name": name,
        "identifiers": ids,
        "issues": issues,
        "amount": c.get("amount"),
    }


def group_key(substrates, products):
    if not substrates or not products or any(s is None for s in substrates + products):
        return None
    return hashlib.sha256(
        stable([sorted(substrates), sorted(products)]).encode()
    ).hexdigest()[:20]


def temperature(v):
    if "value" not in v:
        return None
    if v.get("units") == "CELSIUS":
        return v["value"]
    if v.get("units") == "KELVIN":
        return round(v["value"] - 273.15, 8)
    if v.get("units") == "FAHRENHEIT":
        return round((v["value"] - 32) * 5 / 9, 8)
    return None


def duration(v):
    scales = {"SECOND": 1 / 3600, "MINUTE": 1 / 60, "HOUR": 1, "DAY": 24}
    return (
        v["value"] * scales[v["units"]]
        if "value" in v and v.get("units") in scales
        else None
    )


def quantity(value, original, unit):
    return {
        "value": value,
        "label": f"{value:g} {unit}" if value is not None else "Unavailable",
        "original": original,
    }


def components_condition(components):
    if not components:
        return {"value": None, "label": "Unavailable", "original": []}
    vals, labels = [], []
    for c in components:
        x = compound(c)
        explicit_none = x["name"].lower() == "none" and any(
            i.get("value", "").endswith("_empty") for i in x["identifiers"]
        )
        identity = "EXPLICIT_NONE" if explicit_none else x["smiles"]
        amount = c.get("amount", {})
        if not explicit_none and not any(
            "value" in amount.get(k, {}) and amount[k].get("units")
            for k in ("moles", "mass", "volume")
        ):
            return {
                "value": None,
                "label": x["name"] + " (amount unavailable)",
                "original": components,
            }
        # A custom code alone cannot establish chemical identity.
        if identity is None:
            return {
                "value": None,
                "label": x["name"] + " (identity unavailable)",
                "original": components,
            }
        vals.append({"identity": identity, "amount": c.get("amount")})
        units = {
            "MICROMOLE": "µmol",
            "MOLE": "mol",
            "MICROLITER": "µL",
            "MILLILITER": "mL",
            "MILLIGRAM": "mg",
        }
        q = next(
            (
                v
                for k, v in amount.items()
                if k in ("moles", "mass", "volume") and "value" in v
            ),
            {},
        )
        suffix = (
            f" · {q['value']:g} {units.get(q['units'], q['units'])}"
            if q and not explicit_none
            else ""
        )
        labels.append(("Explicitly none" if explicit_none else x["name"]) + suffix)
    from collections import Counter

    counts = Counter(labels)
    display = " + ".join(
        (f"{n} × " if n > 1 else "") + name for name, n in sorted(counts.items())
    )
    return {"value": sorted(vals, key=stable), "label": display, "original": components}


def yield_measurements(r):
    candidates = []
    for oi, outcome in enumerate(r.get("outcomes", [])):
        for pi, p in enumerate(outcome.get("products", [])):
            if not p.get("is_desired_product"):
                continue
            for mi, m in enumerate(p.get("measurements", [])):
                if m.get("type") != "YIELD" or "value" not in m.get("percentage", {}):
                    continue
                v = m["percentage"]["value"]
                analysis = outcome.get("analyses", {}).get(m.get("analysis_key"), {})
                candidates.append(
                    {
                        "value": v,
                        "valid": math.isfinite(v) and 0 <= v <= 100,
                        "type": "YIELD",
                        "unit": "%",
                        "original": m,
                        "analysis": analysis,
                        "analysis_key": m.get("analysis_key"),
                        "kind": "isolated"
                        if analysis.get("is_of_isolated_species")
                        else "analytical"
                        if "is_of_isolated_species" in analysis
                        else "unspecified",
                        "reaction_time": outcome.get("reaction_time"),
                        "outcome_index": oi,
                        "product_index": pi,
                        "measurement_index": mi,
                        "product": compound(p),
                    }
                )
    # Latest known time, then authentic-standard calibration, then stable source position.
    candidates.sort(
        key=lambda m: (
            -(
                duration(m["reaction_time"] or {})
                if duration(m["reaction_time"] or {}) is not None
                else -1
            ),
            -int(m["original"].get("uses_authentic_standard", False)),
            m["outcome_index"],
            m["product_index"],
            m["measurement_index"],
        )
    )
    return candidates


def readable_condition(field, original):
    if not original:
        return "Unavailable"
    if field == "atmosphere":
        atm = original.get("atmosphere", {})
        control = original.get("control", {})
        return (
            " · ".join(
                v
                for v in [
                    atm.get("details") or atm.get("type", "").replace("_", " ").lower(),
                    control.get("type", "").replace("_", " ").lower(),
                ]
                if v
            )
            or "Recorded pressure details (inspect source)"
        )
    rate = original.get("rate", {}).get("rpm")
    return (
        " · ".join(
            v
            for v in [
                original.get("type", "").replace("_", " ").lower(),
                f"{rate:g} rpm" if rate is not None else "",
                original.get("details", ""),
            ]
            if v
        )
        or "Recorded stirring details (inspect source)"
    )


def normalize(r, row):
    diagnostics = []
    bins = {f: [] for f in ("catalyst", "ligand", "base", "solvent", "other")}
    substrates = []
    substrate_components = []
    for input_name, inp in r.get("inputs", {}).items():
        for c in inp.get("components", []):
            role = c.get("reaction_role")
            if role == "REACTANT":
                substrates.append(compound(c))
                substrate_components.append(c)
            elif role == "SOLVENT":
                bins["solvent"].append(c)
            elif (
                any(
                    i.get("details") == "Lig_ChemTypeIdx"
                    for i in c.get("identifiers", [])
                )
                and input_name == "ligand soln"
            ):
                bins["ligand"].append(c)
            elif (
                any(
                    i.get("details") == "Cat_ChemTypeIdx"
                    for i in c.get("identifiers", [])
                )
                and input_name == "catalyst soln"
            ):
                bins["catalyst"].append(c)
            elif (
                any(
                    i.get("details") == "Base_ChemTypeIdx"
                    for i in c.get("identifiers", [])
                )
                and input_name == "base"
            ):
                bins["base"].append(c)
            else:
                bins["other"].append(c)
                diagnostics.append("unclassified_input")
    products = [
        compound(p)
        for o in r.get("outcomes", [])
        for p in o.get("products", [])
        if p.get("is_desired_product")
    ]
    unique_products = {p["smiles"]: p for p in products}
    products = list(unique_products.values())
    gid = group_key([c["smiles"] for c in substrates], [c["smiles"] for c in products])
    if len(substrates) != 2 or len(products) != 1 or diagnostics:
        gid = None
    if gid is None:
        diagnostics.append("unsafe_strict_identity")
    measurements = yield_measurements(r)
    primary = measurements[0] if measurements else None
    if not primary:
        diagnostics.append("missing_yield")
    if primary and not primary["valid"]:
        diagnostics.append("out_of_range_yield")
    if len(measurements) > 1:
        diagnostics.append("multiple_yield_measurements")
    ambiguous_yield = bool(
        primary
        and any(
            m["reaction_time"] == primary["reaction_time"]
            and (m["value"] != primary["value"] or m["analysis"] != primary["analysis"])
            for m in measurements[1:]
        )
    )
    if ambiguous_yield:
        diagnostics.append("conflicting_yield_measurements")
    diagnostics.extend(
        issue for c in substrates + products for issue in c.get("issues", [])
    )
    conditions = {f: components_condition(v) for f, v in bins.items()}
    conditions["substrate_amounts"] = components_condition(substrate_components)
    # Inventory absence is a defined recorded state, not a claim of physical absence.
    if not bins["other"]:
        conditions["other"] = {
            "value": [],
            "label": "No other inputs recorded",
            "original": [],
        }
    cond = r.get("conditions", {})
    t = cond.get("temperature", {}).get("setpoint", {})
    rt = primary.get("reaction_time") or {} if primary else {}
    conditions["temperature"] = quantity(temperature(t), t, "°C")
    conditions["duration"] = quantity(duration(rt), rt, "h")
    for field, original in [
        ("atmosphere", cond.get("pressure")),
        ("stirring", cond.get("stirring")),
    ]:
        conditions[field] = {
            "value": original or None,
            "label": readable_condition(field, original),
            "original": original,
        }
    for f, c in conditions.items():
        if c["value"] is None:
            diagnostics.append("missing_" + f)
    return {
        "id": r.get("reaction_id") or f"missing-id-row-{row}",
        "group_id": gid,
        "source_row": row,
        "substrates": sorted(substrates, key=lambda c: c["smiles"] or ""),
        "products": products,
        "yield_value": primary["value"]
        if primary and primary["valid"] and not ambiguous_yield
        else None,
        "primary_measurement": primary,
        "measurements": measurements,
        "conditions": conditions,
        "diagnostics": diagnostics,
        "source_identifiers": r.get("identifiers", []),
        "setup": r.get("setup"),
        "provenance": {"doi": r.get("provenance", {}).get("doi")},
        "dataset_id": DATASET_ID,
        "source_summary": {
            "measurement_types": [
                m.get("type", "UNSPECIFIED")
                for o in r.get("outcomes", [])
                for p in o.get("products", [])
                for m in p.get("measurements", [])
            ],
            "roles": [
                c.get("reaction_role", "UNSPECIFIED")
                for inp in r.get("inputs", {}).values()
                for c in inp.get("components", [])
            ],
        },
    }
