"""Tests for PrimeFactorizationScenario."""

from __future__ import annotations

import json
import math
from functools import reduce

import pytest

from ophamin.measuring.proof import EmpiricalProofRecord, REFUTED, VALIDATED
from ophamin.measuring.scenarios.prime_factorization import (
    PrimeFactorizationScenario,
)
from ophamin.measuring.scenarios.prime_structure import (
    _identity_prime_from_canonical,
    _is_prime,
)


def _make_factorizable_trajectory(tmp_path, *, stamp: int = 7,
                                  p_thermo_factors: tuple = (3, 5, 7, 11)):
    """Build a synthetic trajectory where composites perfectly factor as
    p_thermo × p_identity × stamp with primes for stamp + p_thermo."""
    assert _is_prime(stamp), "stamp must be prime for valid factorization"
    for t in p_thermo_factors:
        assert _is_prime(t), f"p_thermo {t} must be prime"

    concept_pool = ["alpha", "beta", "gamma", "delta", "epsilon"]
    traj = []
    for cycle in range(20):
        # 3 concepts per cycle, deterministic from cycle index
        walk = [concept_pool[(cycle + i) % len(concept_pool)] for i in range(3)]
        chain = []
        for j, c in enumerate(walk):
            p_id = _identity_prime_from_canonical(c)
            p_thermo = p_thermo_factors[(cycle + j) % len(p_thermo_factors)]
            composite = p_thermo * p_id * stamp
            chain.append(composite)
        traj.append({
            "cycle_index": cycle,
            "stimulus": "test",
            "trajectory_walk": walk,
            "prime_chain": chain,
            "substrate_state_stamp": stamp,  # match for the SSS test
        })
    out = tmp_path / "factorizable.json"
    out.write_text(json.dumps({"kimera_commit": "synthetic", "trajectory": traj}))
    return out


def test_constructor_validates_path(tmp_path):
    with pytest.raises(FileNotFoundError):
        PrimeFactorizationScenario(trajectory_path=str(tmp_path / "missing.json"))


def test_constructor_validates_threshold(tmp_path):
    p = _make_factorizable_trajectory(tmp_path)
    with pytest.raises(ValueError, match="p_identity_invariance_floor"):
        PrimeFactorizationScenario(trajectory_path=str(p),
                                    p_identity_invariance_floor=1.5)
    with pytest.raises(ValueError, match="p_identity_invariance_floor"):
        PrimeFactorizationScenario(trajectory_path=str(p),
                                    p_identity_invariance_floor=0.0)


def test_score_unreachable(tmp_path):
    p = _make_factorizable_trajectory(tmp_path)
    s = PrimeFactorizationScenario(trajectory_path=str(p))
    with pytest.raises(NotImplementedError):
        s.score([], [])


def test_perfect_p_identity_invariance_validates(tmp_path):
    """Synthetic trajectory has deterministic concept names → 100% invariance."""
    p = _make_factorizable_trajectory(tmp_path)
    s = PrimeFactorizationScenario(trajectory_path=str(p),
                                    p_identity_invariance_floor=0.99)
    proof = s.run()
    assert proof.verdict.outcome == VALIDATED
    assert proof.verdict.observed_value == 1.0


def test_full_factorization_recovery_on_synthetic_trajectory(tmp_path):
    """Synthetic chains constructed as p_thermo × p_identity × stamp should
    GCD-recover the stamp 100% of the time (when p_thermo varies across j)."""
    p = _make_factorizable_trajectory(tmp_path, stamp=7,
                                      p_thermo_factors=(3, 5, 11))
    s = PrimeFactorizationScenario(trajectory_path=str(p))
    proof = s.run()
    u4 = proof.evidence[0].detail["u4_full_factorization"]
    # All 20 cycles probed
    assert u4["n_cycles_probed"] == 20
    # All cycles recover the stamp = 7 (which is prime)
    assert u4["recovered_stamp_prime_rate"] == 1.0
    # All p_thermo (3, 5, 11) are prime
    assert u4["p_thermo_all_prime_rate"] == 1.0


def test_substrate_state_stamp_provenance_section(tmp_path):
    """The U5 sub-section must report sss prime rate + range + match-rate."""
    p = _make_factorizable_trajectory(tmp_path, stamp=7)
    s = PrimeFactorizationScenario(trajectory_path=str(p))
    proof = s.run()
    u5 = proof.evidence[0].detail["u5_substrate_state_stamp"]
    # Synthetic trajectory has substrate_state_stamp = 7 in every cycle (prime!)
    assert u5["sss_prime_rate"] == 1.0
    # 7 is in [100, 49100]? No — outside lower bound
    assert u5["sss_in_identity_range_rate"] == 0.0
    # And in this synthetic case, recovered Arachne stamp = 7 = sss
    assert u5["sss_matches_recovered_stamp_rate"] == 1.0


def test_p_identity_invariance_failure_when_concept_names_mismatch(tmp_path):
    """If a concept name appears with two normalizations producing different
    p_identities, invariance < 1.0. (Not really possible with a deterministic
    function, so we synthesize the failure mode at the test data layer.)"""
    # NB: with a deterministic p_identity, the only way to get < 100% invariance
    # is if the concept name itself differs. So we test the floor enforcement
    # rather than a real failure mode (which is by-construction impossible).
    p = _make_factorizable_trajectory(tmp_path)
    s = PrimeFactorizationScenario(trajectory_path=str(p),
                                    p_identity_invariance_floor=0.5)
    proof = s.run()
    # Should still be VALIDATED at floor=0.5 since invariance = 1.0
    assert proof.verdict.outcome == VALIDATED


def test_signed_proof_carries_provenance(tmp_path):
    p = _make_factorizable_trajectory(tmp_path)
    s = PrimeFactorizationScenario(trajectory_path=str(p))
    proof = s.run()
    assert proof.signature
    agents = proof.provenance.get("agent", {})
    assert "ophamin:kimera-swm" in agents


def test_evidence_records_p_thermo_distribution(tmp_path):
    """P_thermo stats are present in evidence.detail."""
    p = _make_factorizable_trajectory(tmp_path, p_thermo_factors=(3, 5, 11))
    s = PrimeFactorizationScenario(trajectory_path=str(p))
    proof = s.run()
    u4 = proof.evidence[0].detail["u4_full_factorization"]
    for k in ("p_thermo_n_total", "p_thermo_unique_values", "p_thermo_min",
              "p_thermo_max", "p_thermo_median", "p_thermo_mean",
              "p_thermo_distribution_top10"):
        assert k in u4
    # All recovered p_thermo should be from the original set {3, 5, 11}
    p_thermo_values = {v for v, _ in u4["p_thermo_distribution_top10"]}
    assert p_thermo_values <= {3, 5, 11}


def test_trajectory_with_no_factorizable_cycles(tmp_path):
    """Trajectory where chains are too short to GCD → cycles_probed = 0."""
    traj = [
        {"cycle_index": i, "stimulus": "x", "trajectory_walk": ["alpha"],
         "prime_chain": [_identity_prime_from_canonical("alpha")]}
        for i in range(5)
    ]
    p = tmp_path / "single.json"
    p.write_text(json.dumps({"kimera_commit": "x", "trajectory": traj}))
    s = PrimeFactorizationScenario(trajectory_path=str(p))
    proof = s.run()
    u4 = proof.evidence[0].detail["u4_full_factorization"]
    # Each cycle has only 1 q value (chain length 1) → cycles_probed = 0
    assert u4["n_cycles_probed"] == 0


def test_empty_trajectory_raises(tmp_path):
    p = tmp_path / "empty.json"
    p.write_text(json.dumps({"kimera_commit": "x", "trajectory": []}))
    s = PrimeFactorizationScenario(trajectory_path=str(p))
    with pytest.raises(ValueError, match="trajectory is empty"):
        s.run()
