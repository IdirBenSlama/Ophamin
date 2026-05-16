"""Tests for MemoryAsDeformationScenario (Round M, 2026-05-16)."""

from __future__ import annotations

import json

import pytest

from ophamin.measuring.proof import EmpiricalProofRecord, REFUTED, VALIDATED
from ophamin.measuring.scenarios.memory_as_deformation import (
    MemoryAsDeformationScenario,
)


def _make_trajectory(
    tmp_path,
    *,
    cycles: list[dict] | None = None,
):
    """Build synthetic per_cycle trajectory."""
    if cycles is None:
        # Default: 4 cycles, with re-exposure of cycle 0 at cycle 2
        cycles = [
            {
                "cycle": 0, "stimulus": "alpha",
                "concepts_sample": ["a", "b", "c"], "concepts_count": 3,
                "phi": 0.50, "halt_reason": "exhausted",
            },
            {
                "cycle": 1, "stimulus": "beta",
                "concepts_sample": ["x", "y"], "concepts_count": 2,
                "phi": 0.40, "halt_reason": "selective",
            },
            {
                "cycle": 2, "stimulus": "alpha",
                "concepts_sample": ["a", "b", "c"], "concepts_count": 3,
                "phi": 0.51, "halt_reason": "amplitude_death",  # halt flipped
            },
            {
                "cycle": 3, "stimulus": "beta",
                "concepts_sample": ["x", "y"], "concepts_count": 2,
                "phi": 0.41, "halt_reason": "selective",  # halt stable
            },
        ]
    out = tmp_path / "synth.json"
    out.write_text(json.dumps({
        "kimera_commit": "synthetic_commit_sha",
        "per_cycle": cycles,
    }))
    return out


def test_constructor_validates_path(tmp_path):
    with pytest.raises(FileNotFoundError):
        MemoryAsDeformationScenario(trajectory_path=str(tmp_path / "missing.json"))


def test_constructor_validates_threshold(tmp_path):
    p = _make_trajectory(tmp_path)
    with pytest.raises(ValueError, match="concept_jaccard_floor"):
        MemoryAsDeformationScenario(
            trajectory_path=str(p), concept_jaccard_floor=0.0,
        )


def test_score_unreachable(tmp_path):
    p = _make_trajectory(tmp_path)
    s = MemoryAsDeformationScenario(trajectory_path=str(p))
    with pytest.raises(NotImplementedError):
        s.score([], [])


def test_perfect_recognition_validates(tmp_path):
    """All re-exposures have identical concepts → jaccard=1.0 → VALIDATED."""
    p = _make_trajectory(tmp_path)
    s = MemoryAsDeformationScenario(
        trajectory_path=str(p), concept_jaccard_floor=0.85,
    )
    proof = s.run()
    assert proof.verdict.outcome == VALIDATED
    assert proof.verdict.observed_value == 1.0
    # 2 pairs (alpha+alpha, beta+beta); halt flipped in 1 of 2 (alpha)
    detail = proof.evidence[0].detail
    assert detail["n_pairs"] == 2
    assert detail["n_halt_flipped"] == 1
    assert detail["halt_flip_rate"] == 0.5


def test_concept_drift_below_floor_refutes(tmp_path):
    """If re-exposed cycle shares < 85% of concepts → REFUTED."""
    cycles = [
        {"cycle": 0, "stimulus": "alpha", "concepts_sample": ["a", "b", "c", "d"],
         "concepts_count": 4, "phi": 0.5, "halt_reason": "exhausted"},
        {"cycle": 1, "stimulus": "alpha",
         "concepts_sample": ["e", "f", "g", "h"],  # NO overlap
         "concepts_count": 4, "phi": 0.5, "halt_reason": "exhausted"},
    ]
    p = _make_trajectory(tmp_path, cycles=cycles)
    s = MemoryAsDeformationScenario(
        trajectory_path=str(p), concept_jaccard_floor=0.85,
    )
    proof = s.run()
    assert proof.verdict.outcome == REFUTED
    assert proof.verdict.observed_value == 0.0


def test_phi_delta_characterization_recorded(tmp_path):
    """phi delta metrics are computed and recorded in detail."""
    p = _make_trajectory(tmp_path)
    s = MemoryAsDeformationScenario(trajectory_path=str(p))
    proof = s.run()
    detail = proof.evidence[0].detail
    assert "phi_delta_abs_mean" in detail
    assert "phi_delta_abs_max" in detail
    # alpha-alpha: |0.51 - 0.50| = 0.01; beta-beta: |0.41 - 0.40| = 0.01
    assert abs(detail["phi_delta_abs_mean"] - 0.01) < 1e-9
    assert abs(detail["phi_delta_abs_max"] - 0.01) < 1e-9


def test_no_reexposure_pairs_raises(tmp_path):
    """If no two cycles share a stimulus → cannot run."""
    cycles = [
        {"cycle": 0, "stimulus": "unique_a", "concepts_sample": ["a"],
         "concepts_count": 1, "phi": 0.5, "halt_reason": "exhausted"},
        {"cycle": 1, "stimulus": "unique_b", "concepts_sample": ["b"],
         "concepts_count": 1, "phi": 0.5, "halt_reason": "exhausted"},
    ]
    p = _make_trajectory(tmp_path, cycles=cycles)
    s = MemoryAsDeformationScenario(trajectory_path=str(p))
    with pytest.raises(ValueError, match="no re-exposure pairs"):
        s.run()


def test_proof_signs_correctly(tmp_path):
    """Signed proof is verifiable."""
    p = _make_trajectory(tmp_path)
    s = MemoryAsDeformationScenario(trajectory_path=str(p))
    proof = s.run()
    assert proof.signature
    # Verify by re-serializing + deserializing via file
    proof_path = tmp_path / "proof.json"
    proof.to_json(str(proof_path))
    restored = EmpiricalProofRecord.from_json(str(proof_path))
    assert restored.proof_id == proof.proof_id


def test_per_pair_records_match_pair_count(tmp_path):
    """Detail's per_pair_records has same length as n_pairs."""
    p = _make_trajectory(tmp_path)
    s = MemoryAsDeformationScenario(trajectory_path=str(p))
    proof = s.run()
    detail = proof.evidence[0].detail
    assert len(detail["per_pair_records"]) == detail["n_pairs"]


def test_halt_flip_detection(tmp_path):
    """Halt flips are detected per-pair."""
    cycles = [
        {"cycle": 0, "stimulus": "a", "concepts_sample": ["x"], "concepts_count": 1,
         "phi": 0.5, "halt_reason": "exhausted"},
        {"cycle": 1, "stimulus": "a", "concepts_sample": ["x"], "concepts_count": 1,
         "phi": 0.5, "halt_reason": "selective"},  # FLIP
    ]
    p = _make_trajectory(tmp_path, cycles=cycles)
    s = MemoryAsDeformationScenario(trajectory_path=str(p))
    proof = s.run()
    detail = proof.evidence[0].detail
    assert detail["n_halt_flipped"] == 1
    assert detail["halt_flip_rate"] == 1.0
    assert detail["per_pair_records"][0]["halt_flipped"] is True


def test_multiple_reexposures_of_same_stimulus(tmp_path):
    """Re-exposing the same stimulus 3 times yields 3 pairs."""
    cycles = [
        {"cycle": 0, "stimulus": "z", "concepts_sample": ["a"], "concepts_count": 1,
         "phi": 0.5, "halt_reason": "exhausted"},
        {"cycle": 1, "stimulus": "z", "concepts_sample": ["a"], "concepts_count": 1,
         "phi": 0.51, "halt_reason": "exhausted"},
        {"cycle": 2, "stimulus": "z", "concepts_sample": ["a"], "concepts_count": 1,
         "phi": 0.52, "halt_reason": "exhausted"},
    ]
    p = _make_trajectory(tmp_path, cycles=cycles)
    s = MemoryAsDeformationScenario(trajectory_path=str(p))
    proof = s.run()
    # C(3, 2) = 3 pairs
    assert proof.evidence[0].detail["n_pairs"] == 3
