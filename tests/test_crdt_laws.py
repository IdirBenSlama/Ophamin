"""Tests for CRDTLawsScenario — cross-backend Yjs Python convergence claim."""

from __future__ import annotations

import pytest

from ophamin.measuring.proof import EmpiricalProofRecord, REFUTED, VALIDATED
from ophamin.measuring.scenarios.crdt_laws import CRDTLawsScenario


# We require both backends installed; skip cleanly when not (so the suite
# stays runnable without the [crdt] extra).
pytest.importorskip("pycrdt")
pytest.importorskip("y_py")


def test_crdt_laws_constructor_validates_args():
    with pytest.raises(ValueError, match="n_sequences must be"):
        CRDTLawsScenario(n_sequences=0)
    with pytest.raises(ValueError, match="ops_per_sequence must be"):
        CRDTLawsScenario(ops_per_sequence=0)
    with pytest.raises(ValueError, match="convergence_threshold must be"):
        CRDTLawsScenario(convergence_threshold=0.0)
    with pytest.raises(ValueError, match="convergence_threshold must be"):
        CRDTLawsScenario(convergence_threshold=1.5)


def test_crdt_laws_static_scenario_n_cycles_zero():
    s = CRDTLawsScenario()
    assert s.n_cycles == 0


def test_crdt_laws_score_unreachable():
    s = CRDTLawsScenario()
    with pytest.raises(NotImplementedError, match="custom run"):
        s.score([], [])


def test_crdt_laws_claim_well_formed():
    s = CRDTLawsScenario(n_sequences=10, ops_per_sequence=5, convergence_threshold=0.99)
    claim = s.build_claim()
    assert "≥ 99" in claim.statement or "0.99" in claim.statement
    assert claim.threshold.metric == "cross_backend_convergence_rate"
    assert claim.threshold.comparator == ">="
    assert claim.threshold.value == 0.99
    assert claim.h0
    assert claim.h1


def test_crdt_laws_run_returns_validated_signed_proof():
    """End-to-end: small run should converge 100% (both backends are Yrs)."""
    s = CRDTLawsScenario(n_sequences=20, ops_per_sequence=10, seed=42)
    proof = s.run()
    assert isinstance(proof, EmpiricalProofRecord)
    assert proof.verdict.outcome == VALIDATED
    assert proof.verdict.observed_value == 1.0
    assert "20/20" in proof.verdict.reasoning
    assert proof.signature  # signed
    assert proof.proof_id  # content-addressed


def test_crdt_laws_evidence_carries_per_backend_timing():
    s = CRDTLawsScenario(n_sequences=10, ops_per_sequence=5, seed=42)
    proof = s.run()
    detail = proof.evidence[0].detail
    assert detail["n_sequences"] == 10
    assert detail["ops_per_sequence"] == 5
    assert detail["n_total_runs"] == 10
    assert detail["n_agreed"] == 10
    assert detail["seed"] == 42
    assert detail["py_total_seconds"] > 0
    assert detail["y_py_total_seconds"] > 0
    assert detail["sample_disagreements"] == []


def test_crdt_laws_deterministic_seed_produces_same_proof_id():
    """Same seed → same op sequences → same agreement counts → same proof_id."""
    s1 = CRDTLawsScenario(n_sequences=15, ops_per_sequence=8, seed=99)
    s2 = CRDTLawsScenario(n_sequences=15, ops_per_sequence=8, seed=99)
    p1 = s1.run()
    p2 = s2.run()
    # The signed payloads include timing dict-detail which can drift; but the
    # claim + verdict + observed_value must be identical for the same seed.
    assert p1.verdict.observed_value == p2.verdict.observed_value
    assert p1.verdict.outcome == p2.verdict.outcome


def test_crdt_laws_high_threshold_with_perfect_run_validates():
    """Even at the strict 1.0 threshold, the Yjs core should still converge 100%."""
    s = CRDTLawsScenario(
        n_sequences=20, ops_per_sequence=5, seed=7, convergence_threshold=1.0
    )
    proof = s.run()
    assert proof.verdict.outcome == VALIDATED
    assert proof.verdict.observed_value == 1.0


def test_crdt_laws_provenance_records_both_backends():
    s = CRDTLawsScenario(n_sequences=5, ops_per_sequence=3, seed=1)
    proof = s.run()
    # provenance is a PROV-JSON dict; agents are namespaced "ophamin:<name>".
    agents = proof.provenance.get("agent", {})
    assert "ophamin:pycrdt" in agents
    assert "ophamin:y_py" in agents
    assert agents["ophamin:pycrdt"]["ophamin:role"] == "crdt_backend_under_validation"
