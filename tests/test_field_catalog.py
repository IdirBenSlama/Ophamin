"""Tests for the field catalog + scenario field-contract layer."""

from __future__ import annotations

import pytest

from ophamin.seeing.substrate.field_catalog import (
    CATALOG_BY_NAME,
    CATALOG_FAMILIES,
    KIMERA_FIELD_CATALOG,
    CatalogedField,
    ContractViolation,
    FieldContract,
    ScenarioFieldContract,
    catalog_by_family,
    catalog_coverage,
    cataloged,
    validate_contract_against_raw,
)


# --------------------------------------------------------------------------
# Catalog structural invariants
# --------------------------------------------------------------------------


def test_catalog_is_nonempty_and_contains_load_bearing_fields():
    assert len(KIMERA_FIELD_CATALOG) >= 25
    # Fields scenarios actually use today MUST be in the catalog
    load_bearing = {
        "phi_value", "walker_halt_mode", "cycle_seconds", "gwf_blocked",
        "manipulation_detected", "concepts_count", "prime_chain",
        "dissonance_events_count",
    }
    catalog_names = {f.name for f in KIMERA_FIELD_CATALOG}
    assert load_bearing <= catalog_names


def test_every_catalog_field_has_known_family():
    for f in KIMERA_FIELD_CATALOG:
        assert f.family in CATALOG_FAMILIES, f"unknown family {f.family!r} on {f.name!r}"


def test_catalog_by_name_index_is_consistent():
    assert len(CATALOG_BY_NAME) == len(KIMERA_FIELD_CATALOG), \
        "duplicate field names in catalog"
    for f in KIMERA_FIELD_CATALOG:
        assert CATALOG_BY_NAME[f.name] is f


def test_catalog_field_descriptions_are_nonempty():
    for f in KIMERA_FIELD_CATALOG:
        assert f.description.strip(), f"empty description on {f.name!r}"
        assert len(f.description) > 20, f"trivially-short description on {f.name!r}"


def test_catalog_field_types_are_nonempty():
    for f in KIMERA_FIELD_CATALOG:
        assert f.types, f"empty types on {f.name!r}"


# --------------------------------------------------------------------------
# CatalogedField construction
# --------------------------------------------------------------------------


def test_cataloged_field_rejects_empty_name():
    with pytest.raises(ValueError, match="name cannot be empty"):
        CatalogedField(name="", types=("int",), family="phi", description="x")


def test_cataloged_field_rejects_empty_types():
    with pytest.raises(ValueError, match="types cannot be empty"):
        CatalogedField(name="x", types=(), family="phi", description="x")


def test_cataloged_field_rejects_unknown_family():
    with pytest.raises(ValueError, match="not in"):
        CatalogedField(name="x", types=("int",), family="totally_made_up",
                       description="x")


def test_cataloged_field_to_dict_round_trip():
    f = KIMERA_FIELD_CATALOG[0]
    d = f.to_dict()
    assert d["name"] == f.name
    assert d["family"] == f.family
    assert tuple(d["types"]) == f.types


# --------------------------------------------------------------------------
# CatalogedField.accepts_value type-matching
# --------------------------------------------------------------------------


def test_phi_value_accepts_float_and_int_and_none():
    phi = cataloged("phi_value")
    assert phi is not None
    assert phi.accepts_value(0.7)
    assert phi.accepts_value(1)
    assert phi.accepts_value(None)        # nullable
    assert not phi.accepts_value("0.7")
    assert not phi.accepts_value([0.7])


def test_walker_halt_mode_accepts_str_and_none():
    halt = cataloged("walker_halt_mode")
    assert halt is not None
    assert halt.accepts_value("exhausted")
    assert halt.accepts_value(None)
    assert not halt.accepts_value(0)


def test_gwf_blocked_accepts_bool():
    gwf = cataloged("gwf_blocked")
    assert gwf is not None
    assert gwf.accepts_value(True)
    assert gwf.accepts_value(False)
    assert gwf.accepts_value(None)


def test_prime_chain_accepts_list():
    pc = cataloged("prime_chain")
    assert pc is not None
    assert pc.accepts_value([1, 2, 3])
    assert pc.accepts_value([])
    assert not pc.accepts_value("123")


def test_int_field_does_not_accept_bool_unless_declared():
    """Python bools are ints — but the catalog should treat them separately
    when the field is declared `int` only.
    """
    f = CatalogedField(name="x", types=("int",), family="walker", description="x" * 30)
    # int accepts bool only if "bool" is in types — and it isn't here.
    assert not f.accepts_value(True)
    assert f.accepts_value(7)


def test_non_nullable_field_rejects_none():
    f = CatalogedField(name="x", types=("int",), family="walker",
                       description="x" * 30, nullable=False)
    assert not f.accepts_value(None)
    assert f.accepts_value(0)


# --------------------------------------------------------------------------
# catalog_by_family + cataloged lookup
# --------------------------------------------------------------------------


def test_catalog_by_family_returns_only_that_family():
    walker_fields = catalog_by_family("walker")
    assert len(walker_fields) >= 5      # halt_mode + M1/M2/M3/M4 counters
    for f in walker_fields:
        assert f.family == "walker"


def test_catalog_by_family_unknown_returns_empty():
    assert catalog_by_family("nonexistent") == ()


def test_cataloged_lookup_returns_none_for_unknown():
    assert cataloged("nonexistent_field") is None


def test_cataloged_lookup_returns_field_for_known():
    f = cataloged("phi_value")
    assert f is not None
    assert f.name == "phi_value"


# --------------------------------------------------------------------------
# Scenario field contract — validation
# --------------------------------------------------------------------------


def test_contract_satisfied_when_all_required_fields_present_and_typed():
    contract = ScenarioFieldContract(
        scenario_name="test_scenario",
        contracts=(
            FieldContract(field_name="phi_value"),
            FieldContract(field_name="walker_halt_mode"),
            FieldContract(field_name="cycle_seconds"),
        ),
    )
    raw = {
        "phi_value": 0.621,
        "walker_halt_mode": "exhausted",
        "cycle_seconds": 1.23,
    }
    violations = validate_contract_against_raw(contract, raw)
    assert violations == ()


def test_contract_violation_missing_required_field():
    contract = ScenarioFieldContract(
        scenario_name="test_scenario",
        contracts=(FieldContract(field_name="phi_value"),),
    )
    raw = {"walker_halt_mode": "exhausted"}      # missing phi_value
    violations = validate_contract_against_raw(contract, raw)
    assert len(violations) == 1
    assert violations[0].kind == "missing_required"
    assert violations[0].field_name == "phi_value"
    assert "test_scenario" in violations[0].detail


def test_contract_missing_optional_field_is_not_violation():
    contract = ScenarioFieldContract(
        scenario_name="test_scenario",
        contracts=(FieldContract(field_name="phi_value", required=False),),
    )
    raw = {}
    violations = validate_contract_against_raw(contract, raw)
    assert violations == ()


def test_contract_violation_type_mismatch():
    contract = ScenarioFieldContract(
        scenario_name="test_scenario",
        contracts=(FieldContract(field_name="phi_value"),),
    )
    raw = {"phi_value": "not_a_number"}      # str instead of float
    violations = validate_contract_against_raw(contract, raw)
    assert len(violations) == 1
    assert violations[0].kind == "type_mismatch"
    assert violations[0].field_name == "phi_value"


def test_contract_violation_uncataloged_field():
    contract = ScenarioFieldContract(
        scenario_name="test_scenario",
        contracts=(FieldContract(field_name="brand_new_kimera_field"),),
    )
    raw = {"brand_new_kimera_field": 42}      # present but not in catalog
    violations = validate_contract_against_raw(contract, raw)
    assert len(violations) == 1
    assert violations[0].kind == "uncataloged_required"
    assert "brand_new_kimera_field" in violations[0].detail
    assert "CatalogedField" in violations[0].detail


def test_contract_violation_family_mismatch():
    contract = ScenarioFieldContract(
        scenario_name="test_scenario",
        contracts=(FieldContract(
            field_name="phi_value", expected_family="walker"  # phi_value is "phi"
        ),),
    )
    raw = {"phi_value": 0.7}
    violations = validate_contract_against_raw(contract, raw)
    assert len(violations) == 1
    assert violations[0].kind == "family_mismatch"


def test_contract_with_no_field_dependencies_validates_clean():
    contract = ScenarioFieldContract(scenario_name="empty_scenario", contracts=())
    violations = validate_contract_against_raw(contract, {"any": "raw"})
    assert violations == ()


def test_contract_aggregates_multiple_violations():
    contract = ScenarioFieldContract(
        scenario_name="test",
        contracts=(
            FieldContract(field_name="phi_value"),
            FieldContract(field_name="cycle_seconds"),
            FieldContract(field_name="walker_halt_mode"),
        ),
    )
    raw = {"phi_value": "wrong_type"}      # type mismatch + 2 missing
    violations = validate_contract_against_raw(contract, raw)
    assert len(violations) == 3
    kinds = {v.kind for v in violations}
    assert kinds == {"type_mismatch", "missing_required"}


# --------------------------------------------------------------------------
# Coverage diagnostic
# --------------------------------------------------------------------------


def test_catalog_coverage_with_full_raw_dict():
    raw = {
        "phi_value": 0.7,
        "walker_halt_mode": "exhausted",
        "cycle_seconds": 1.0,
        "unknown_kimera_field": 42,            # uncataloged
        "another_unknown": "x",
    }
    cov = catalog_coverage(raw)
    assert cov["in_catalog"] == 3
    assert cov["uncataloged"] == 2
    assert "phi_value" in cov["in_catalog_names"]
    assert "unknown_kimera_field" in cov["uncataloged_names"]
    assert cov["catalog_size"] == len(KIMERA_FIELD_CATALOG)
    assert cov["raw_size"] == 5


def test_catalog_coverage_with_empty_raw():
    cov = catalog_coverage({})
    assert cov["in_catalog"] == 0
    assert cov["uncataloged"] == 0
    assert cov["missing_from_raw"] == len(KIMERA_FIELD_CATALOG)


def test_catalog_coverage_reports_missing_from_raw():
    raw = {"phi_value": 0.7}      # 1 cataloged field present
    cov = catalog_coverage(raw)
    assert cov["missing_from_raw"] == len(KIMERA_FIELD_CATALOG) - 1
    assert "phi_value" not in cov["missing_from_raw_names"]
    assert "walker_halt_mode" in cov["missing_from_raw_names"]


# --------------------------------------------------------------------------
# ContractViolation serialisation
# --------------------------------------------------------------------------


def test_contract_violation_to_dict():
    v = ContractViolation(field_name="x", kind="missing_required", detail="d")
    d = v.to_dict()
    assert d == {"field_name": "x", "kind": "missing_required", "detail": "d"}


def test_scenario_field_contract_to_dict():
    c = ScenarioFieldContract(
        scenario_name="s",
        contracts=(FieldContract(field_name="x"),
                   FieldContract(field_name="y", required=False),),
    )
    d = c.to_dict()
    assert d["scenario_name"] == "s"
    assert len(d["contracts"]) == 2
    assert d["contracts"][0]["field_name"] == "x"
    assert d["contracts"][0]["required"] is True
    assert d["contracts"][1]["required"] is False


def test_scenario_field_contract_field_names():
    c = ScenarioFieldContract(
        scenario_name="s",
        contracts=(FieldContract("x"), FieldContract("y"), FieldContract("z")),
    )
    assert c.field_names() == ("x", "y", "z")
