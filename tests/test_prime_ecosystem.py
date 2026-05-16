"""Tests for PrimeEcosystemScenario."""

from __future__ import annotations

import json

import pytest

from ophamin.measuring.proof import EmpiricalProofRecord, REFUTED, VALIDATED
from ophamin.measuring.scenarios.prime_ecosystem import PrimeEcosystemScenario


def _make_synthetic_trajectory(
    tmp_path,
    n_cycles: int = 30,
    *,
    persistent_keys: int = 6,
    qbe_bimodal: bool = True,
    iev_count_distribution: tuple[int, ...] = (3, 3, 4, 4, 4),
):
    """Build a synthetic trajectory with controlled prime-ecosystem features.

    `persistent_keys`: number of fused-key labels that appear in EVERY cycle.
    `qbe_bimodal`: if True, half cycles have qbe=0, half have qbe=3.5.
    `iev_count_distribution`: tuple of iev counts to cycle through.
    """
    persistent_labels = [f"Fused(persistent_{i}_a+persistent_{i}_b)"
                         for i in range(persistent_keys)]
    traj = []
    for i in range(n_cycles):
        # Every cycle has the persistent keys; plus 2 cycle-specific keys
        fused = {label: 100 + (j * 7) for j, label in enumerate(persistent_labels)}
        fused[f"Fused(ephemeral_{i}_a+ephemeral_{i}_b)"] = 500
        # qbe bimodal: cycle 0,2,4... = 0; cycle 1,3,5... = 3.5
        qbe = (3.5 if (qbe_bimodal and i % 2 == 1) else 0.0)
        iev = iev_count_distribution[i % len(iev_count_distribution)]
        traj.append({
            "cycle_index": i,
            "stimulus": f"stim_{i}",
            "alexandria_fused_primes": fused,
            "quantum_prime_basis_entropy": qbe,
            "internal_event_primes_assigned_this_cycle": iev,
            "last_internal_event_prime": 1000003 + i,
        })
    out = tmp_path / "synth.json"
    out.write_text(json.dumps({"kimera_commit": "synthetic", "trajectory": traj}))
    return out


def test_constructor_validates_path(tmp_path):
    with pytest.raises(FileNotFoundError):
        PrimeEcosystemScenario(trajectory_path=str(tmp_path / "missing.json"))


def test_constructor_validates_threshold(tmp_path):
    p = _make_synthetic_trajectory(tmp_path)
    with pytest.raises(ValueError, match="fused_prime_persistence_threshold"):
        PrimeEcosystemScenario(trajectory_path=str(p),
                               fused_prime_persistence_threshold=1.5)


def test_constructor_validates_n_top_k(tmp_path):
    p = _make_synthetic_trajectory(tmp_path)
    with pytest.raises(ValueError, match="n_top_k_fused"):
        PrimeEcosystemScenario(trajectory_path=str(p), n_top_k_fused=0)


def test_score_unreachable(tmp_path):
    p = _make_synthetic_trajectory(tmp_path)
    s = PrimeEcosystemScenario(trajectory_path=str(p))
    with pytest.raises(NotImplementedError):
        s.score([], [])


def test_persistent_fused_keys_validates(tmp_path):
    """6 persistent keys present in every cycle → VALIDATED at threshold=5."""
    p = _make_synthetic_trajectory(tmp_path, n_cycles=30, persistent_keys=6)
    s = PrimeEcosystemScenario(trajectory_path=str(p),
                               fused_prime_persistence_threshold=0.90,
                               n_top_k_fused=5)
    proof = s.run()
    assert proof.verdict.outcome == VALIDATED
    assert proof.verdict.observed_value >= 5


def test_few_persistent_fused_keys_refutes(tmp_path):
    """Only 2 persistent keys → REFUTED at threshold=5."""
    p = _make_synthetic_trajectory(tmp_path, n_cycles=30, persistent_keys=2)
    s = PrimeEcosystemScenario(trajectory_path=str(p),
                               fused_prime_persistence_threshold=0.90,
                               n_top_k_fused=5)
    proof = s.run()
    assert proof.verdict.outcome == REFUTED
    assert proof.verdict.observed_value < 5


def test_bimodal_qbe_indicator(tmp_path):
    """Synthetic 50/50 bimodal qbe → stdev/mean > 0.8 → bimodal indicator TRUE."""
    p = _make_synthetic_trajectory(tmp_path, n_cycles=30, qbe_bimodal=True)
    s = PrimeEcosystemScenario(trajectory_path=str(p))
    proof = s.run()
    q = proof.evidence[0].detail["u7_quantum_basis_entropy"]
    assert q["bimodal_indicator"] is True
    assert q["n_at_zero"] >= 10  # ~half should be 0
    assert q["n_above_3nat"] >= 10  # ~half should be ≥ 3


def test_iev_distribution_matches_ev37(tmp_path):
    """Most cycles fire ≥ 3 internal events → matches_ev37 = True."""
    # Default distribution (3,3,4,4,4) → 100% fire ≥ 3
    p = _make_synthetic_trajectory(tmp_path, n_cycles=30)
    s = PrimeEcosystemScenario(trajectory_path=str(p))
    proof = s.run()
    i = proof.evidence[0].detail["u8_internal_event_primes"]
    assert i["matches_ev37_expectation"] is True
    assert i["rate_firing_3_or_more"] == 1.0


def test_iev_low_distribution_does_not_match_ev37(tmp_path):
    """Most cycles fire ≤ 2 internal events → matches_ev37 = False."""
    p = _make_synthetic_trajectory(tmp_path, n_cycles=30,
                                   iev_count_distribution=(0, 1, 1, 2))
    s = PrimeEcosystemScenario(trajectory_path=str(p))
    proof = s.run()
    i = proof.evidence[0].detail["u8_internal_event_primes"]
    assert i["matches_ev37_expectation"] is False
    assert i["rate_firing_3_or_more"] == 0.0


def test_signed_proof_carries_provenance(tmp_path):
    p = _make_synthetic_trajectory(tmp_path)
    s = PrimeEcosystemScenario(trajectory_path=str(p))
    proof = s.run()
    assert proof.signature
    agents = proof.provenance.get("agent", {})
    assert "ophamin:kimera-swm" in agents


def test_empty_trajectory_raises(tmp_path):
    p = tmp_path / "empty.json"
    p.write_text(json.dumps({"kimera_commit": "x", "trajectory": []}))
    s = PrimeEcosystemScenario(trajectory_path=str(p))
    with pytest.raises(ValueError, match="trajectory is empty"):
        s.run()
