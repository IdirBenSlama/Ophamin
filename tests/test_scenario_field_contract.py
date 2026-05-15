"""Tests for Scenario.field_contract() — the opt-in field-dependency gate."""

from __future__ import annotations

import pytest

from ophamin.measuring.proof import Claim, DatasetRef, PillarEvidence, Threshold
from ophamin.measuring.scenarios.base import (
    Scenario,
    ScenarioFieldContractViolation,
    ScenarioScore,
)
from ophamin.seeing.corpus import CorpusRecord
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest
from ophamin.seeing.substrate.field_catalog import (
    FieldContract,
    ScenarioFieldContract,
)


# --------------------------------------------------------------------------
# Test scaffolding — a fake corpus + a fake substrate emitting controllable
# raw dicts so we can drive contract violations deterministically.
# --------------------------------------------------------------------------


class _FakeCorpus:
    def __init__(self, name: str = "fake", n: int = 3) -> None:
        self.name = name
        self._records = [
            CorpusRecord(id=str(i), text=f"item-{i}", metadata={})
            for i in range(n)
        ]

    def require_available(self) -> None:
        pass

    def records(self):
        return iter(self._records)

    def dataset_ref(self) -> DatasetRef:
        return DatasetRef(
            name=self.name,
            content_hash="0" * 64,
            n_records=len(self._records),
            source="test",
            kind="fake",
        )


class _FakeSubstrate(SubstrateUnderTest):
    name = "fake"

    def __init__(self, raw_per_cycle: dict) -> None:
        super().__init__()
        self._raw = raw_per_cycle

    def git_commit(self) -> str:
        return ""

    def reset(self) -> None:
        pass

    def run_cycle(self, stimulus, params=None) -> CycleResult:
        return CycleResult(cycle_index=0, success=True, raw=dict(self._raw))

    def run_batch(self, stimuli, params=None) -> list[CycleResult]:
        return [
            CycleResult(cycle_index=i, success=True, raw=dict(self._raw))
            for i in range(len(stimuli))
        ]


def _make_scenario_class(scenario_name: str, contract: ScenarioFieldContract | None):
    """Build a minimal Scenario subclass for testing."""

    _CONTRACT = contract

    class _TestScenario(Scenario):
        name = scenario_name
        corpus_name = "fake"
        target = "entity"
        n_cycles = 3

        def build_claim(self):
            return Claim(
                statement="test claim",
                operationalization="test op",
                threshold=Threshold(metric="test_metric", comparator=">=", value=0.5),
                h0="null: observed < threshold",
                h1="alt: observed >= threshold",
            )

        def score(self, cycle_results, records):
            return ScenarioScore(observed_value=1.0, evidence=[], reasoning="ok")

        def field_contract(self):
            return _CONTRACT

    return _TestScenario


def _patch_get_corpus(monkeypatch, corpus):
    """Make scenario.run() pick up our fake corpus."""
    monkeypatch.setattr(
        "ophamin.measuring.scenarios.base.get_corpus",
        lambda name, data_root=None: corpus,
    )


# --------------------------------------------------------------------------
# Default behavior — no contract = no gate (back-compat)
# --------------------------------------------------------------------------


def test_scenario_with_no_contract_runs_to_proof_record(monkeypatch):
    """The default field_contract()=None must not gate anything."""
    Cls = _make_scenario_class("no_contract", contract=None)
    s = Cls()
    _patch_get_corpus(monkeypatch, _FakeCorpus())
    substrate = _FakeSubstrate(raw_per_cycle={"phi_value": 0.7})
    record = s.run(substrate)
    assert record.verdict.outcome in ("VALIDATED", "REFUTED", "INCONCLUSIVE")


# --------------------------------------------------------------------------
# Contract satisfied — no exception, scenario proceeds
# --------------------------------------------------------------------------


def test_scenario_with_satisfied_contract_runs_clean(monkeypatch):
    contract = ScenarioFieldContract(
        scenario_name="happy",
        contracts=(
            FieldContract(field_name="phi_value"),
            FieldContract(field_name="walker_halt_mode"),
        ),
    )
    Cls = _make_scenario_class("happy", contract=contract)
    s = Cls()
    _patch_get_corpus(monkeypatch, _FakeCorpus())
    substrate = _FakeSubstrate(raw_per_cycle={
        "phi_value": 0.65,
        "walker_halt_mode": "exhausted",
    })
    record = s.run(substrate)
    assert record.verdict.outcome in ("VALIDATED", "REFUTED", "INCONCLUSIVE")


# --------------------------------------------------------------------------
# Contract violation — loud failure
# --------------------------------------------------------------------------


def test_missing_required_field_raises_contract_violation(monkeypatch):
    contract = ScenarioFieldContract(
        scenario_name="strict",
        contracts=(FieldContract(field_name="phi_value", required=True),),
    )
    Cls = _make_scenario_class("strict", contract=contract)
    s = Cls()
    _patch_get_corpus(monkeypatch, _FakeCorpus())
    # Substrate emits raw without phi_value.
    substrate = _FakeSubstrate(raw_per_cycle={"walker_halt_mode": "exhausted"})
    with pytest.raises(ScenarioFieldContractViolation) as excinfo:
        s.run(substrate)
    assert excinfo.value.scenario_name == "strict"
    assert any(v.field_name == "phi_value" for v in excinfo.value.violations)


def test_type_mismatch_raises_contract_violation(monkeypatch):
    contract = ScenarioFieldContract(
        scenario_name="strict",
        contracts=(FieldContract(field_name="walker_halt_mode"),),
    )
    Cls = _make_scenario_class("strict", contract=contract)
    s = Cls()
    _patch_get_corpus(monkeypatch, _FakeCorpus())
    substrate = _FakeSubstrate(raw_per_cycle={"walker_halt_mode": 42})  # int, not str
    with pytest.raises(ScenarioFieldContractViolation):
        s.run(substrate)


def test_optional_missing_field_does_not_raise(monkeypatch):
    contract = ScenarioFieldContract(
        scenario_name="lax",
        contracts=(FieldContract(field_name="phi_value", required=False),),
    )
    Cls = _make_scenario_class("lax", contract=contract)
    s = Cls()
    _patch_get_corpus(monkeypatch, _FakeCorpus())
    substrate = _FakeSubstrate(raw_per_cycle={})  # missing, but optional
    record = s.run(substrate)
    assert record.verdict.outcome in ("VALIDATED", "REFUTED", "INCONCLUSIVE")


def test_uncataloged_required_field_does_not_raise(monkeypatch):
    """uncataloged_required is informational — not fatal. The catalog hasn't
    been extended yet for this field, but the field IS present in raw."""
    contract = ScenarioFieldContract(
        scenario_name="hint",
        contracts=(FieldContract(field_name="brand_new_field"),),
    )
    Cls = _make_scenario_class("hint", contract=contract)
    s = Cls()
    _patch_get_corpus(monkeypatch, _FakeCorpus())
    substrate = _FakeSubstrate(raw_per_cycle={"brand_new_field": 42})
    record = s.run(substrate)
    # Did NOT raise — uncataloged is informational.
    assert record.verdict.outcome in ("VALIDATED", "REFUTED", "INCONCLUSIVE")


def test_contract_violation_message_is_actionable():
    """The exception message must name the scenario AND the violating fields,
    so an operator can debug from the log alone."""
    contract = ScenarioFieldContract(
        scenario_name="debug_me",
        contracts=(
            FieldContract(field_name="phi_value"),
            FieldContract(field_name="walker_halt_mode"),
        ),
    )
    # Pre-build the violation manually (don't need to run a scenario).
    from ophamin.seeing.substrate.field_catalog import validate_contract_against_raw
    raw = {}
    violations = validate_contract_against_raw(contract, raw)
    exc = ScenarioFieldContractViolation("debug_me", violations)
    msg = str(exc)
    assert "debug_me" in msg
    assert "phi_value" in msg
    assert "walker_halt_mode" in msg
    assert "missing_required" in msg
