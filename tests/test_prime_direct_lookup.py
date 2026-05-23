"""Tests for PrimeDirectLookupScenario."""

from __future__ import annotations

import json

import pytest

from ophamin.measuring.proof import REFUTED, VALIDATED
from ophamin.measuring.scenarios.prime_direct_lookup import (
    PrimeDirectLookupScenario,
)


def _make_synthetic_trajectory(
    tmp_path,
    *,
    n_cycles: int = 20,
    p_thermo_per_cycle: tuple[int, ...] = (2, 3, 5, 7, 11),
    stamp_per_cycle: int = 47,
    force_non_prime_p_thermo: bool = False,
):
    """Build a synthetic trajectory with arachne_lookup data matching capture script shape."""
    traj = []
    for cycle in range(n_cycles):
        lookups = []
        for j, pt in enumerate(p_thermo_per_cycle):
            pt_value = pt if not force_non_prime_p_thermo else (pt + 1)  # break primality
            lookups.append({
                "concept": f"concept_{cycle}_{j}",
                "found": True,
                "composite": pt_value * 101 * stamp_per_cycle,
                "p_thermo": pt_value,
                "p_identity": 101,
                "substrate_state_stamp": stamp_per_cycle,
                "canonical": f"concept_{cycle}_{j}",
            })
        traj.append({
            "cycle_index": cycle,
            "stimulus": "test",
            "raw": {},
            "per_concept_arachne_lookup": lookups,
            "arachne_internal_stamp_after_cycle": stamp_per_cycle,
        })
    out = tmp_path / "synth.json"
    out.write_text(json.dumps({"kimera_commit": "synthetic", "trajectory": traj}))
    return out


def test_constructor_validates_path(tmp_path):
    with pytest.raises(FileNotFoundError):
        PrimeDirectLookupScenario(trajectory_path=str(tmp_path / "missing.json"))


def test_constructor_validates_thresholds(tmp_path):
    p = _make_synthetic_trajectory(tmp_path)
    with pytest.raises(ValueError, match="p_thermo_prime_rate_floor"):
        PrimeDirectLookupScenario(trajectory_path=str(p),
                                   p_thermo_prime_rate_floor=1.5)
    with pytest.raises(ValueError, match="p_thermo_median_floor"):
        PrimeDirectLookupScenario(trajectory_path=str(p),
                                   p_thermo_median_floor=1)


def test_score_unreachable(tmp_path):
    p = _make_synthetic_trajectory(tmp_path)
    s = PrimeDirectLookupScenario(trajectory_path=str(p))
    with pytest.raises(NotImplementedError):
        s.score([], [])


def test_all_prime_p_thermo_validates(tmp_path):
    """All p_thermo values are primes (2, 3, 5, 7, 11) → 100% prime-rate → VALIDATED."""
    p = _make_synthetic_trajectory(tmp_path,
                                    p_thermo_per_cycle=(2, 3, 5, 7, 11))
    s = PrimeDirectLookupScenario(trajectory_path=str(p),
                                   p_thermo_prime_rate_floor=0.95)
    proof = s.run()
    assert proof.verdict.outcome == VALIDATED
    assert proof.verdict.observed_value == 1.0


def test_non_prime_p_thermo_refutes(tmp_path):
    """Forced non-prime p_thermo → REFUTED."""
    p = _make_synthetic_trajectory(tmp_path,
                                    p_thermo_per_cycle=(2, 3, 5, 7, 11),
                                    force_non_prime_p_thermo=True)
    s = PrimeDirectLookupScenario(trajectory_path=str(p),
                                   p_thermo_prime_rate_floor=0.95)
    proof = s.run()
    # 2+1=3 is prime, but 3+1=4, 5+1=6, 7+1=8, 11+1=12 are not. Of 5 values,
    # only 1 (3) is prime → 20% prime-rate → REFUTED
    assert proof.verdict.outcome == REFUTED


def test_stamp_uniformity_per_cycle_100pct(tmp_path):
    """Synthetic single-stamp-per-cycle → 100% uniformity."""
    p = _make_synthetic_trajectory(tmp_path, stamp_per_cycle=47)
    s = PrimeDirectLookupScenario(trajectory_path=str(p))
    proof = s.run()
    u = proof.evidence[0].detail["stamp_uniformity_per_cycle"]
    assert u["rate"] == 1.0


def test_p_thermo_summary_carries_stats(tmp_path):
    p = _make_synthetic_trajectory(tmp_path)
    s = PrimeDirectLookupScenario(trajectory_path=str(p))
    proof = s.run()
    pt = proof.evidence[0].detail["p_thermo_summary"]
    for k in ("n", "n_prime", "prime_rate", "median", "mean", "min", "max",
              "unique", "top_10"):
        assert k in pt


def test_round_h_resolution_recorded(tmp_path):
    """The Round H U4 puzzle's root cause is documented in evidence."""
    p = _make_synthetic_trajectory(tmp_path)
    s = PrimeDirectLookupScenario(trajectory_path=str(p))
    proof = s.run()
    resolution = proof.evidence[0].detail["round_h_resolution"]
    assert "GCD" in resolution
    assert "artefact" in resolution.lower()


def test_signed_proof_carries_provenance(tmp_path):
    p = _make_synthetic_trajectory(tmp_path)
    s = PrimeDirectLookupScenario(trajectory_path=str(p))
    proof = s.run()
    assert proof.signature
    agents = proof.provenance.get("agent", {})
    assert "ophamin:kimera-swm" in agents


def test_no_lookups_raises(tmp_path):
    """Trajectory missing per_concept_arachne_lookup → loud-fail."""
    p = tmp_path / "empty.json"
    p.write_text(json.dumps({"kimera_commit": "x", "trajectory": [
        {"cycle_index": 0, "stimulus": "x"},
    ]}))
    s = PrimeDirectLookupScenario(trajectory_path=str(p))
    with pytest.raises(RuntimeError, match="No p_thermo values"):
        s.run()


def test_empty_trajectory_raises(tmp_path):
    p = tmp_path / "empty.json"
    p.write_text(json.dumps({"kimera_commit": "x", "trajectory": []}))
    s = PrimeDirectLookupScenario(trajectory_path=str(p))
    with pytest.raises(ValueError, match="trajectory is empty"):
        s.run()
