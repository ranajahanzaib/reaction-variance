"""Synthetic fixtures are confined to tests and never imported into production data."""

from copy import deepcopy

import pytest
from app.comparison import compare, insights
from app.normalization import (
    FIELDS,
    canonical,
    components_condition,
    duration,
    group_key,
    normalize,
    temperature,
)


@pytest.fixture
def source():
    def c(smi, name, role, code=None):
        return {
            "identifiers": [
                {"type": "SMILES", "value": smi},
                {"type": "NAME", "value": name},
            ]
            + ([{"type": "CUSTOM", "details": code, "value": "test"}] if code else []),
            "reaction_role": role,
            "amount": {"moles": {"value": 1, "units": "MOLE"}},
        }

    return {
        "reaction_id": "fixture-a",
        "inputs": {
            "reactants": {
                "components": [
                    c("CCBr", "bromoethane", "REACTANT"),
                    c("N", "ammonia", "REACTANT"),
                ]
            },
            "catalyst soln": {
                "components": [c("[Pd]", "Pd", "CATALYST", "Cat_ChemTypeIdx")]
            },
            "ligand soln": {
                "components": [c("P", "phosphine", "CATALYST", "Lig_ChemTypeIdx")]
            },
            "base": {
                "components": [c("[K+].[OH-]", "KOH", "REAGENT", "Base_ChemTypeIdx")]
            },
            "solvent": {"components": [c("O", "water", "SOLVENT")]},
        },
        "conditions": {
            "temperature": {"setpoint": {"value": 80, "units": "CELSIUS"}},
            "pressure": {"atmosphere": {"type": "NITROGEN"}},
            "stirring": {"type": "AGITATION"},
        },
        "outcomes": [
            {
                "reaction_time": {"value": 18, "units": "HOUR"},
                "products": [
                    {
                        "identifiers": [{"type": "SMILES", "value": "CCN"}],
                        "is_desired_product": True,
                        "measurements": [
                            {
                                "type": "YIELD",
                                "percentage": {"value": 50},
                                "analysis_key": "test",
                            }
                        ],
                    }
                ],
                "analyses": {"test": {"type": "LCMS", "is_of_isolated_species": False}},
            }
        ],
    }


def test_identity():
    assert canonical("OCC") == canonical("CCO")
    assert canonical("CCO") != canonical("COC")
    assert canonical("N[C@@H](C)O") != canonical("N[C@H](C)O")
    assert canonical("[13CH3]O") != canonical("CO")
    assert canonical("[Na+].[Cl-]") != canonical("Cl")
    assert group_key(["CC", "N"], ["CCN"]) == group_key(["N", "CC"], ["CCN"])
    assert group_key(["CC", None], ["CCN"]) is None
    assert group_key(["CC"], []) is None


def test_roles(source):
    a = normalize(source, 0)
    source["inputs"]["catalyst soln"]["components"][0]["identifiers"][0]["value"] = (
        "[Ni]"
    )
    source["inputs"]["solvent"]["components"][0]["identifiers"][0]["value"] = "CCO"
    assert normalize(source, 1)["group_id"] == a["group_id"]
    source["inputs"]["unknown"] = {
        "components": [{"reaction_role": "REAGENT", "identifiers": []}]
    }
    assert normalize(source, 2)["group_id"] is None


def test_no_product(source):
    source["outcomes"][0]["products"][0]["identifiers"] = []
    assert normalize(source, 0)["group_id"] is None


@pytest.mark.parametrize(
    "value,expected", [(0, 0), (50, 50), (100, 100), (101, None), (-1, None)]
)
def test_yields(source, value, expected):
    source["outcomes"][0]["products"][0]["measurements"][0]["percentage"]["value"] = (
        value
    )
    r = normalize(source, 0)
    assert r["yield_value"] == expected
    assert r["measurements"][0]["value"] == value
    if expected is None:
        assert "out_of_range_yield" in r["diagnostics"]


@pytest.mark.parametrize("mutation", ["area", "missing", "side_product"])
def test_not_yield(source, mutation):
    p = source["outcomes"][0]["products"][0]
    if mutation == "area":
        p["measurements"][0]["type"] = "AREA"
    if mutation == "missing":
        p["measurements"][0]["percentage"] = {}
    if mutation == "side_product":
        p["is_desired_product"] = False
    assert normalize(source, 0)["yield_value"] is None


def test_multiple(source):
    later = deepcopy(source["outcomes"][0])
    later["reaction_time"]["value"] = 24
    later["products"][0]["measurements"][0]["percentage"]["value"] = 72.123
    source["outcomes"].append(later)
    r = normalize(source, 0)
    assert r["yield_value"] == 72.123 and len(r["measurements"]) == 2
    assert r["primary_measurement"]["original"]["percentage"]["value"] == 72.123
    assert "multiple_yield_measurements" in r["diagnostics"]


def test_units():
    assert temperature({"value": 353.15, "units": "KELVIN"}) == temperature(
        {"value": 80, "units": "CELSIUS"}
    )
    assert duration({"value": 60, "units": "MINUTE"}) == duration(
        {"value": 1, "units": "HOUR"}
    )
    assert duration({}) is None and temperature({}) is None


def test_none_and_solvent():
    none = {
        "identifiers": [
            {"type": "NAME", "value": "none"},
            {"type": "CUSTOM", "value": "L_empty"},
        ]
    }
    assert components_condition([none])["value"] is not None
    assert components_condition([])["value"] is None
    a = {
        "identifiers": [{"type": "SMILES", "value": "O"}],
        "amount": {"volume": {"value": 1, "units": "MILLILITER"}},
    }
    b = {
        "identifiers": [{"type": "SMILES", "value": "CCO"}],
        "amount": {"volume": {"value": 1, "units": "MILLILITER"}},
    }
    assert (
        components_condition([a, b])["value"] == components_condition([b, a])["value"]
    )
    assert components_condition([a, b])["value"] != components_condition([a])["value"]


@pytest.mark.parametrize(
    "fields,category",
    [
        ([], "exact_recorded_conditions"),
        (["ligand"], "single_recorded_factor"),
        (["ligand", "temperature"], "multiple_recorded_factors"),
    ],
)
def test_comparison(source, fields, category):
    a = normalize(source, 0)
    b = deepcopy(a)
    b["id"] = "fixture-b"
    b["yield_value"] = 75
    for f in fields:
        b["conditions"][f]["value"] = "different"
    result = compare(a, b)
    assert (
        result["classification"] == category and result["delta_percentage_points"] == 25
    )
    assert result["differences"] == [f for f in FIELDS if f in fields]
    assert "not causes" in result["caveat"]


@pytest.mark.parametrize("field", ["temperature", "catalyst"])
def test_unknown(source, field):
    a = normalize(source, 0)
    a["conditions"][field]["value"] = None
    assert compare(a, a)["classification"] == "incomplete"
    assert field in compare(a, a)["missing"]


def test_unrelated_and_measurement(source):
    a = normalize(source, 0)
    b = deepcopy(a)
    b["group_id"] = "another-product"
    assert compare(a, b)["classification"] == "not_comparable"
    b["group_id"] = a["group_id"]
    b["primary_measurement"]["type"] = "AREA"
    r = compare(a, b)
    assert r["classification"] == "incomplete" and r["delta_percentage_points"] is None


def test_unknown_vs_none(source):
    a = normalize(source, 0)
    b = deepcopy(a)
    a["conditions"]["ligand"]["value"] = None
    b["conditions"]["ligand"]["value"] = "EXPLICIT_NONE"
    assert compare(a, b)["classification"] == "incomplete"


def test_identical_and_insights(source):
    a = normalize(source, 0)
    assert compare(a, a)["classification"] == "exact_recorded_conditions"
    b = deepcopy(a)
    b["id"] = "b"
    b["conditions"]["ligand"]["value"] = "changed"
    b["yield_value"] = 90
    result = insights([a, b])
    assert result["single_factor"][0]["delta"] == 40


def test_missing_component_amount_is_unknown():
    c = {"identifiers": [{"type": "SMILES", "value": "O"}]}
    assert components_condition([c])["value"] is None


def test_conflicting_yields(source):
    m = deepcopy(source["outcomes"][0]["products"][0]["measurements"][0])
    m["percentage"]["value"] = 65
    source["outcomes"][0]["products"][0]["measurements"].append(m)
    r = normalize(source, 0)
    assert (
        r["yield_value"] is None
        and "conflicting_yield_measurements" in r["diagnostics"]
    )
    assert compare(r, r)["classification"] == "incomplete"


def test_invalid_and_ambiguous_identifiers(source):
    c = source["inputs"]["reactants"]["components"][0]
    c["identifiers"].append({"type": "SMILES", "value": "invalid"})
    assert normalize(source, 0)["group_id"] is None


def test_missing_method_is_incomplete(source):
    del source["outcomes"][0]["analyses"]["test"]["is_of_isolated_species"]
    r = normalize(source, 0)
    assert compare(r, r)["classification"] == "incomplete"


def test_substrate_quantity_is_a_recorded_factor(source):
    a = normalize(source, 0)
    source["reaction_id"] = "fixture-b"
    source["inputs"]["reactants"]["components"][0]["amount"]["moles"]["value"] = 2
    b = normalize(source, 1)
    result = compare(a, b)
    assert result["strict_match"]
    assert result["classification"] == "single_recorded_factor"
    assert result["differences"] == ["substrate_amounts"]
