"""Tests for PrimeCrossInstanceScenario."""

from __future__ import annotations

import json

import pytest

from ophamin.measuring.proof import EmpiricalProofRecord, REFUTED, VALIDATED
from ophamin.measuring.scenarios.prime_cross_instance import (
    PrimeCrossInstanceScenario,
)


def _make_cross_instance_trajectory(
    tmp_path,
    n_instances: int = 3,
    *,
    concept_to_p_identity: dict[str, int] | None = None,
    p_thermo_variation: bool = False,
    stamp_variation: bool = False,
):
    """Build synthetic cross-instance trajectory."""
    if concept_to_p_identity is None:
        concept_to_p_identity = {f"concept_{i}": 101 + i * 2 for i in range(10)}
    per_instance_results = []
    for inst in range(n_instances):
        per_concept = {}
        for concept, p_id in concept_to_p_identity.items():
            per_concept[concept] = {
                "p_identity": p_id,  # always the same (deterministic)
                "p_thermo": 3 + (inst if p_thermo_variation else 0),
                "substrate_state_stamp": 47 + (inst if stamp_variation else 0),
                "composite": p_id * (3 + (inst if p_thermo_variation else 0)) * (47 + (inst if stamp_variation else 0)),
                "canonical": concept,
            }
        per_instance_results.append({
            "instance_id": inst,
            "per_concept_primes": per_concept,
        })
    out = tmp_path / "synth.json"
    out.write_text(json.dumps({
        "kimera_commit": "synthetic",
        "n_instances": n_instances,
        "per_instance_results": per_instance_results,
    }))
    return out


def test_constructor_validates_path(tmp_path):
    with pytest.raises(FileNotFoundError):
        PrimeCrossInstanceScenario(trajectory_path=str(tmp_path / "missing.json"))


def test_constructor_validates_threshold(tmp_path):
    p = _make_cross_instance_trajectory(tmp_path)
    with pytest.raises(ValueError, match="p_identity_invariance_floor"):
        PrimeCrossInstanceScenario(trajectory_path=str(p),
                                    p_identity_invariance_floor=0.0)


def test_score_unreachable(tmp_path):
    p = _make_cross_instance_trajectory(tmp_path)
    s = PrimeCrossInstanceScenario(trajectory_path=str(p))
    with pytest.raises(NotImplementedError):
        s.score([], [])


def test_perfect_p_identity_invariance_validates(tmp_path):
    """All instances share same p_identity for each concept → 100% → VALIDATED."""
    p = _make_cross_instance_trajectory(tmp_path, n_instances=4)
    s = PrimeCrossInstanceScenario(trajectory_path=str(p),
                                    p_identity_invariance_floor=0.99)
    proof = s.run()
    assert proof.verdict.outcome == VALIDATED
    assert proof.verdict.observed_value == 1.0


def test_p_thermo_variation_does_not_break_p_identity_verdict(tmp_path):
    """Even with p_thermo varying, p_identity remains invariant → VALIDATED."""
    p = _make_cross_instance_trajectory(tmp_path, n_instances=4,
                                         p_thermo_variation=True)
    s = PrimeCrossInstanceScenario(trajectory_path=str(p))
    proof = s.run()
    assert proof.verdict.outcome == VALIDATED  # p_identity still 100%
    d = proof.evidence[0].detail
    assert d["p_identity_invariance"]["rate"] == 1.0
    assert d["p_thermo_invariance"]["rate"] < 1.0  # varying → < 100%


def test_invariance_records_carry_per_factor_data(tmp_path):
    p = _make_cross_instance_trajectory(tmp_path)
    s = PrimeCrossInstanceScenario(trajectory_path=str(p))
    proof = s.run()
    d = proof.evidence[0].detail
    for k in ("p_identity_invariance", "p_thermo_invariance",
              "stamp_invariance", "composite_invariance"):
        assert k in d
        assert "rate" in d[k]
        assert "n_invariant" in d[k]


def test_non_invariant_p_thermo_concepts_surfaced(tmp_path):
    """When p_thermo varies, the non-invariant sample list is populated."""
    p = _make_cross_instance_trajectory(tmp_path, n_instances=4,
                                         p_thermo_variation=True)
    s = PrimeCrossInstanceScenario(trajectory_path=str(p))
    proof = s.run()
    d = proof.evidence[0].detail
    assert len(d["non_invariant_p_thermo_sample"]) > 0


def test_signed_proof_carries_provenance(tmp_path):
    p = _make_cross_instance_trajectory(tmp_path)
    s = PrimeCrossInstanceScenario(trajectory_path=str(p))
    proof = s.run()
    assert proof.signature
    agents = proof.provenance.get("agent", {})
    assert "ophamin:kimera-swm" in agents


def test_no_instances_raises(tmp_path):
    """Trajectory with no per_instance_results → raise."""
    p = tmp_path / "empty.json"
    p.write_text(json.dumps({"kimera_commit": "x", "per_instance_results": []}))
    s = PrimeCrossInstanceScenario(trajectory_path=str(p))
    with pytest.raises(ValueError, match="no per_instance_results"):
        s.run()


def test_concept_only_in_one_instance_excluded(tmp_path):
    """Concepts seen in only 1 instance don't contribute to invariance."""
    instances = [
        {"instance_id": 0, "per_concept_primes": {
            "shared": {"p_identity": 101, "p_thermo": 2, "substrate_state_stamp": 47, "composite": 101*2*47, "canonical": "shared"},
            "only_in_0": {"p_identity": 103, "p_thermo": 2, "substrate_state_stamp": 47, "composite": 103*2*47, "canonical": "only_in_0"},
        }},
        {"instance_id": 1, "per_concept_primes": {
            "shared": {"p_identity": 101, "p_thermo": 2, "substrate_state_stamp": 47, "composite": 101*2*47, "canonical": "shared"},
        }},
    ]
    p = tmp_path / "asymm.json"
    p.write_text(json.dumps({"kimera_commit": "x", "per_instance_results": instances}))
    s = PrimeCrossInstanceScenario(trajectory_path=str(p))
    proof = s.run()
    d = proof.evidence[0].detail
    # Only "shared" contributes; "only_in_0" excluded
    assert d["n_shared_concepts"] == 1
