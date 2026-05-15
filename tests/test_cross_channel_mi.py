"""Tests for CrossChannelMutualInformationScenario."""

from __future__ import annotations

import json

import pytest

from ophamin.measuring.proof import EmpiricalProofRecord, REFUTED, VALIDATED
from ophamin.measuring.scenarios.cross_channel_mutual_information import (
    CrossChannelMutualInformationScenario,
    DEFAULT_PAIRS,
)


pytest.importorskip("pyitlib")
pytest.importorskip("ennemi")


def _write_synthetic_trajectory(tmp_path, n_cycles: int = 50, perfect_corr: bool = False):
    """Write a synthetic trajectory for deterministic tests."""
    import math
    import random
    rng = random.Random(0)
    traj = []
    for i in range(n_cycles):
        x = rng.gauss(0.5, 0.1)
        if perfect_corr:
            # phi and tidal_kii perfectly equal → MI maximal
            y = x
        else:
            # phi and tidal_kii independent → MI ~ 0
            y = rng.gauss(0.5, 0.1)
        traj.append({
            "cycle_index": i,
            "phi": x,
            "tidal_kii": y,
            "kuramoto_order_parameter": rng.uniform(0, 1),
            "dissonance_events_count": rng.randint(0, 20),
            "dissonance_score": rng.random(),
            "alexandria_knowledge_mass_cumulative": float(i),  # linear-deterministic
            "arachne_web_coupling_frobenius": rng.gauss(2.0, 0.3),
            "arachne_web_order_parameter": rng.gauss(0.5, 0.1),
            "arachne_web_coupling_top_eigenvalue": rng.gauss(2.0, 0.3),
        })
    out = tmp_path / "synth_traj.json"
    out.write_text(json.dumps({
        "kimera_commit": "synthetic",
        "trajectory": traj,
    }))
    return out


def test_constructor_validates_path(tmp_path):
    with pytest.raises(FileNotFoundError):
        CrossChannelMutualInformationScenario(
            trajectory_path=str(tmp_path / "no-such.json"),
        )


def test_constructor_validates_pairs_nonempty(tmp_path):
    p = _write_synthetic_trajectory(tmp_path)
    with pytest.raises(ValueError, match="pairs cannot be empty"):
        CrossChannelMutualInformationScenario(trajectory_path=str(p), pairs=())


def test_constructor_validates_threshold(tmp_path):
    p = _write_synthetic_trajectory(tmp_path)
    with pytest.raises(ValueError, match="mi_floor_threshold must be"):
        CrossChannelMutualInformationScenario(
            trajectory_path=str(p), mi_floor_threshold=-0.1,
        )


def test_default_pairs_uses_canonical_substrate_names(tmp_path):
    """DEFAULT_PAIRS must reference canonical substrate field names
    (phi not phi_value, etc.) per 2026-05-15 catalog refresh."""
    pair_names = {n for pair in DEFAULT_PAIRS for n in pair}
    # canonical names that should appear
    assert "phi" in pair_names
    # legacy names that should NOT appear
    assert "phi_value" not in pair_names
    assert "walker_halt_mode" not in pair_names
    assert "kii_value" not in pair_names


def test_score_unreachable():
    s = CrossChannelMutualInformationScenario.__new__(
        CrossChannelMutualInformationScenario,
    )
    s.pairs = DEFAULT_PAIRS  # bypass __init__
    with pytest.raises(NotImplementedError):
        s.score([], [])


def test_perfect_correlation_produces_high_mi(tmp_path):
    """If phi == tidal_kii in the trajectory, MI should be high → VALIDATED."""
    p = _write_synthetic_trajectory(tmp_path, n_cycles=50, perfect_corr=True)
    s = CrossChannelMutualInformationScenario(
        trajectory_path=str(p),
        pairs=(("phi", "tidal_kii"),),
        mi_floor_threshold=0.5,  # high threshold; perfect corr should clear it
    )
    proof = s.run()
    assert proof.verdict.outcome == VALIDATED
    assert proof.verdict.observed_value > 0.5


def test_independent_signals_produce_near_zero_mi_in_ennemi_cross_check(tmp_path):
    """Independent gaussians → MI near 0 by the unbiased KSG estimator.

    Note: pyitlib's discretized-Shannon estimator has known finite-sample
    bias on small N + 10-bin discretization (~1 nat spurious MI at N=50).
    The cross-check oracle pattern (pyitlib + ennemi) catches this — ennemi's
    KSG is unbiased at small N. The test asserts on the ennemi value as the
    correctness oracle for independence detection.
    """
    p = _write_synthetic_trajectory(tmp_path, n_cycles=200, perfect_corr=False)
    s = CrossChannelMutualInformationScenario(
        trajectory_path=str(p),
        pairs=(("phi", "tidal_kii"),),
        mi_floor_threshold=0.5,
    )
    proof = s.run()
    rows = proof.evidence[0].detail["per_pair_results"]
    ennemi_mi = rows[0]["mi_ennemi_nats"]
    # ennemi (KSG) is the unbiased estimator; should give ~0 for independence
    assert abs(ennemi_mi) < 0.15, (
        f"ennemi MI for independent gaussians should be ~0, got {ennemi_mi}"
    )


def test_pair_with_insufficient_samples_skipped(tmp_path):
    """Pairs with < 5 paired samples are skipped (reported as skip_reason)."""
    # Trajectory with most fields None
    traj = [
        {"cycle_index": i, "phi": 0.5, "tidal_kii": None}
        for i in range(20)
    ]
    p = tmp_path / "skip.json"
    p.write_text(json.dumps({"kimera_commit": "x", "trajectory": traj}))
    s = CrossChannelMutualInformationScenario(
        trajectory_path=str(p),
        pairs=(("phi", "tidal_kii"),),
        mi_floor_threshold=0.05,
    )
    proof = s.run()
    rows = proof.evidence[0].detail["per_pair_results"]
    assert rows[0]["mi_pyitlib_nats"] is None
    assert "skip_reason" in rows[0]


def test_signed_proof_record_carries_provenance(tmp_path):
    p = _write_synthetic_trajectory(tmp_path, n_cycles=50, perfect_corr=True)
    s = CrossChannelMutualInformationScenario(
        trajectory_path=str(p),
        pairs=(("phi", "tidal_kii"),),
    )
    proof = s.run()
    assert proof.signature
    agents = proof.provenance.get("agent", {})
    assert "ophamin:pyitlib" in agents
    assert "ophamin:ennemi" in agents
    assert "ophamin:kimera-swm" in agents


def test_evidence_records_cross_backend_agreement(tmp_path):
    p = _write_synthetic_trajectory(tmp_path, n_cycles=50, perfect_corr=True)
    s = CrossChannelMutualInformationScenario(
        trajectory_path=str(p),
        pairs=(("phi", "tidal_kii"),),
    )
    proof = s.run()
    detail = proof.evidence[0].detail
    assert "n_pairs_with_both_estimators" in detail
    assert "n_pairs_agree_direction" in detail
    assert detail["n_pairs_with_both_estimators"] == 1
    # perfect-correlation should agree
    assert detail["n_pairs_agree_direction"] == 1


def test_trajectory_missing_trajectory_key_raises(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"kimera_commit": "x"}))  # no "trajectory" key
    s = CrossChannelMutualInformationScenario(
        trajectory_path=str(p),
        pairs=(("phi", "tidal_kii"),),
    )
    with pytest.raises(ValueError, match="must contain a 'trajectory' key"):
        s.run()
