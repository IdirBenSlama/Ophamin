"""Tests for the deterministic-seed-audit scenario (RFC 0002 Phase E4).

Three layers of evidence:

1. **Construction invariants** — the scenario validates its
   ``target_scenario_name`` against the registry + the threshold's
   range at construction.

2. **End-to-end VALIDATED** — running the scenario against the default
   target (``crdt-laws``) produces a signed proof with
   ``outcome == VALIDATED`` and ``cross_check == 'passed'``. The two
   reproducibility-form hashes match.

3. **`reproducibility_hash` invariants** — the helper strips the
   load-bearing list of non-deterministic fields but preserves every
   other byte. We test this directly with hand-crafted proofs that
   differ only in stripped fields (must hash same) AND in load-bearing
   fields (must hash differently).
"""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from ophamin import __version__
from ophamin.measuring.proof.record import (
    Claim,
    DatasetRef,
    EmpiricalProofRecord,
    PillarEvidence,
    PreRegistration,
    Reproduction,
    Threshold,
    Verdict,
    content_hash,
)
from ophamin.measuring.scenarios.deterministic_seed_audit import (
    DeterministicSeedAuditScenario,
    reproducibility_hash,
)
from ophamin.seeing.substrate.mock import MockSubstrate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_minimal_proof(*, statistic_value: float = 0.5, created_at: str | None = None) -> EmpiricalProofRecord:
    """Build a hand-crafted minimal EmpiricalProofRecord for hash-equivalence tests."""
    threshold = Threshold(metric="x", comparator=">=", value=0.5, units="proportion")
    claim = Claim(
        statement="dummy claim",
        operationalization="dummy operationalization",
        threshold=threshold,
        h0="dummy h0",
        h1="dummy h1",
    )
    prereg = PreRegistration(
        config_hash=content_hash({"config": "dummy"}),
        data_hash=content_hash({"data": "dummy"}),
        analysis_plan="dummy plan",
        preregistered_at="2026-05-17T00:00:00+00:00",
    )
    dataset = DatasetRef(
        name="dummy-corpus",
        content_hash=content_hash({"data": "dummy"}),
        n_records=1,
        source="synthetic",
        kind="test",
    )
    evidence = [
        PillarEvidence(
            pillar="test_pillar",
            statistic_name="dummy_metric",
            statistic_value=statistic_value,
            library="pytest",
            library_version="1.0",
            detail={
                "non_timing": "kept",
                "wall_time_seconds": 123.45,  # must be stripped
                "py_total_seconds": 0.001,    # must be stripped
                "ci_method": "wilson_95%",    # must be kept
            },
        )
    ]
    verdict = Verdict.decide(observed=statistic_value, threshold=threshold)
    proof = EmpiricalProofRecord(
        claim=claim,
        preregistration=prereg,
        datasets=[dataset],
        substrate_name="test-substrate",
        substrate_git_commit="deadbeefcafe",
        evidence=evidence,
        verdict=verdict,
        reproduction=Reproduction(command="pytest dummy"),
        ophamin_version=__version__,
        ophamin_git_commit="badf00dface",
        created_at=created_at or datetime.now(timezone.utc).isoformat(),
    )
    return proof


# ---------------------------------------------------------------------------
# Construction invariants
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_default_construction(self) -> None:
        scenario = DeterministicSeedAuditScenario()
        assert scenario.name == "deterministic-seed-audit"
        assert scenario.target_scenario_name == "crdt-laws"
        assert scenario.threshold == 1.0
        assert scenario.target_scenario_kwargs == {
            "n_sequences": 5,
            "ops_per_sequence": 5,
            "seed": 20260517,
        }

    def test_empty_target_scenario_name_rejected(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            DeterministicSeedAuditScenario(target_scenario_name="")

    def test_unknown_target_scenario_name_rejected(self) -> None:
        with pytest.raises(ValueError, match="not registered"):
            DeterministicSeedAuditScenario(target_scenario_name="nonexistent-scenario-xyz")

    def test_invalid_threshold_rejected(self) -> None:
        with pytest.raises(ValueError, match="threshold must be"):
            DeterministicSeedAuditScenario(threshold=0.0)
        with pytest.raises(ValueError, match="threshold must be"):
            DeterministicSeedAuditScenario(threshold=1.5)

    def test_target_kwargs_are_copied_not_aliased(self) -> None:
        """Mutating the input dict after construction must not affect the scenario."""
        kwargs = {"n_sequences": 1, "ops_per_sequence": 1, "seed": 999}
        scenario = DeterministicSeedAuditScenario(target_scenario_kwargs=kwargs)
        kwargs["seed"] = 12345
        assert scenario.target_scenario_kwargs["seed"] == 999

    def test_score_unreachable(self) -> None:
        scenario = DeterministicSeedAuditScenario()
        with pytest.raises(NotImplementedError, match="score\\(\\) is unreachable"):
            scenario.score([], [])


# ---------------------------------------------------------------------------
# End-to-end run produces VALIDATED
# ---------------------------------------------------------------------------


class TestEndToEnd:
    def test_default_run_validates(self) -> None:
        scenario = DeterministicSeedAuditScenario(
            target_scenario_kwargs={
                "n_sequences": 3,
                "ops_per_sequence": 3,
                "seed": 20260517,
            },
        )
        proof = scenario.run(substrate=MockSubstrate(seed=1))
        assert proof.verdict.outcome == "VALIDATED"
        assert proof.verdict.observed_value == 1.0
        assert proof.evidence[0].cross_check == "passed"
        assert proof.evidence[0].statistic_value == 1.0

    def test_run_carries_both_proof_hashes(self) -> None:
        scenario = DeterministicSeedAuditScenario(
            target_scenario_kwargs={
                "n_sequences": 3,
                "ops_per_sequence": 3,
                "seed": 99,
            },
        )
        proof = scenario.run(substrate=MockSubstrate(seed=1))
        detail = proof.evidence[0].detail
        assert "reproducibility_hash_first" in detail
        assert "reproducibility_hash_second" in detail
        assert detail["reproducibility_hash_first"] == detail["reproducibility_hash_second"]
        # The two proof_ids will differ (timestamps), but the reproducibility
        # hashes agree.
        assert detail["first_proof_id"] != detail["second_proof_id"]
        assert detail["verdict_agreement"] is True

    def test_run_signs_proof(self) -> None:
        from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY

        scenario = DeterministicSeedAuditScenario(
            target_scenario_kwargs={
                "n_sequences": 3,
                "ops_per_sequence": 3,
                "seed": 7,
            },
        )
        proof = scenario.run(substrate=MockSubstrate(seed=1))
        assert proof.signature
        assert proof.verify_signature(DEFAULT_SIGN_KEY)

    def test_run_with_none_substrate_falls_back_to_mock(self) -> None:
        """The audit must work without an externally-provided substrate."""
        scenario = DeterministicSeedAuditScenario(
            target_scenario_kwargs={
                "n_sequences": 3,
                "ops_per_sequence": 3,
                "seed": 7,
            },
        )
        proof = scenario.run(substrate=None)
        assert proof.verdict.outcome == "VALIDATED"

    def test_passes_validate(self) -> None:
        scenario = DeterministicSeedAuditScenario(
            target_scenario_kwargs={
                "n_sequences": 3,
                "ops_per_sequence": 3,
                "seed": 7,
            },
        )
        proof = scenario.run(substrate=MockSubstrate(seed=1))
        problems = proof.validate()
        assert problems == [], f"emitted proof failed validate(): {problems}"


# ---------------------------------------------------------------------------
# reproducibility_hash invariants
# ---------------------------------------------------------------------------


class TestReproducibilityHash:
    def test_two_identical_proofs_hash_same(self) -> None:
        proof_a = _make_minimal_proof(created_at="2026-05-17T00:00:00+00:00")
        proof_b = _make_minimal_proof(created_at="2026-05-17T00:00:00+00:00")
        assert reproducibility_hash(proof_a) == reproducibility_hash(proof_b)

    def test_created_at_difference_does_not_change_hash(self) -> None:
        """The whole point: drifting timestamps mustn't affect the hash."""
        proof_a = _make_minimal_proof(created_at="2026-05-17T00:00:00+00:00")
        proof_b = _make_minimal_proof(created_at="2026-12-31T23:59:59+00:00")
        assert reproducibility_hash(proof_a) == reproducibility_hash(proof_b)

    def test_pre_registered_at_difference_does_not_change_hash(self) -> None:
        proof_a = _make_minimal_proof()
        proof_b = _make_minimal_proof()
        # Mutate the pre-registration timestamp on the second.
        proof_b.preregistration = replace(
            proof_b.preregistration,
            preregistered_at="2027-01-01T00:00:00+00:00",
        )
        assert reproducibility_hash(proof_a) == reproducibility_hash(proof_b)

    def test_provenance_difference_does_not_change_hash(self) -> None:
        """PROV-O block carries per-activity timestamps that drift."""
        proof_a = _make_minimal_proof()
        proof_b = _make_minimal_proof()
        proof_b.provenance = {"this": "differs", "but": "shouldnt break the hash"}
        assert reproducibility_hash(proof_a) == reproducibility_hash(proof_b)

    def test_reproduction_command_difference_does_not_change_hash(self) -> None:
        proof_a = _make_minimal_proof()
        proof_b = _make_minimal_proof()
        proof_b.reproduction = Reproduction(command="DIFFERENT /absolute/path/python ...")
        assert reproducibility_hash(proof_a) == reproducibility_hash(proof_b)

    def test_timing_detail_keys_stripped(self) -> None:
        """Keys ending in _seconds / _avg_ms / _wall_time / _perf_counter are stripped."""
        proof_a = _make_minimal_proof()
        proof_b = _make_minimal_proof()
        # The minimal-proof fixture already has wall_time_seconds + py_total_seconds.
        # Verify they hash identically when those values DIFFER:
        proof_b.evidence[0].detail["wall_time_seconds"] = 999.99  # changed from 123.45
        proof_b.evidence[0].detail["py_total_seconds"] = 99.99   # changed from 0.001
        assert reproducibility_hash(proof_a) == reproducibility_hash(proof_b)

    def test_non_timing_detail_difference_changes_hash(self) -> None:
        """Conversely: a real metric-value drift MUST surface in the hash."""
        proof_a = _make_minimal_proof()
        proof_b = _make_minimal_proof()
        proof_b.evidence[0].detail["ci_method"] = "different_method"
        assert reproducibility_hash(proof_a) != reproducibility_hash(proof_b)

    def test_statistic_value_difference_changes_hash(self) -> None:
        """The load-bearing claim: actual measurement drift breaks reproducibility."""
        proof_a = _make_minimal_proof(statistic_value=0.5)
        proof_b = _make_minimal_proof(statistic_value=0.6)
        assert reproducibility_hash(proof_a) != reproducibility_hash(proof_b)

    def test_verdict_difference_changes_hash(self) -> None:
        proof_a = _make_minimal_proof(statistic_value=0.6)  # VALIDATED (>= 0.5)
        proof_b = _make_minimal_proof(statistic_value=0.4)  # REFUTED (< 0.5)
        assert proof_a.verdict.outcome != proof_b.verdict.outcome
        assert reproducibility_hash(proof_a) != reproducibility_hash(proof_b)

    def test_does_not_mutate_input_proof(self) -> None:
        """Hash is pure — calling it twice on the same proof gives the same answer
        AND the proof itself remains intact."""
        proof = _make_minimal_proof()
        # Snapshot the body BEFORE hashing.
        before = copy.deepcopy(proof._body())
        h_1 = reproducibility_hash(proof)
        h_2 = reproducibility_hash(proof)
        # Body is unchanged.
        assert proof._body() == before
        # Hash is deterministic.
        assert h_1 == h_2

    def test_hash_is_64_char_hex(self) -> None:
        proof = _make_minimal_proof()
        h = reproducibility_hash(proof)
        assert len(h) == 64
        # SHA-256 hex output: 0-9 + a-f only.
        assert all(c in "0123456789abcdef" for c in h)


# ---------------------------------------------------------------------------
# Registration in SCENARIOS
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_scenario_is_registered(self) -> None:
        from ophamin.measuring.scenarios.base import SCENARIOS

        assert "deterministic-seed-audit" in SCENARIOS
        assert SCENARIOS["deterministic-seed-audit"] is DeterministicSeedAuditScenario
