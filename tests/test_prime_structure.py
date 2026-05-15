"""Tests for PrimeStructureScenario."""

from __future__ import annotations

import hashlib
import json

import pytest

from ophamin.measuring.proof import EmpiricalProofRecord, REFUTED, VALIDATED
from ophamin.measuring.scenarios.prime_structure import (
    PrimeStructureScenario,
    _identity_prime_from_canonical,
    _is_prime,
)


def _identity_prime_naive(canonical: str) -> int:
    """Naive re-implementation matching ArachneProtocol._identity_prime."""
    h = hashlib.sha256(canonical.encode("utf-8")).digest()
    candidate = (int.from_bytes(h[:4], "big") % 49000) + 100
    while not _is_prime(candidate):
        candidate += 1
    return candidate


def _make_trajectory(tmp_path, *, n_repeated_pairs: int = 5,
                     concept_drift: int = 0, force_factorization_violation: bool = False):
    """Build a synthetic trajectory where same stimulus repeats with a small concept-set drift.

    `concept_drift` = number of concept positions that differ between repeats.
    """
    # Two stimuli, each appearing N times
    stims = ["alpha beta gamma", "delta epsilon zeta"]
    base_concepts = {
        "alpha beta gamma": ["alpha", "beta", "gamma", "extra1", "extra2"],
        "delta epsilon zeta": ["delta", "epsilon", "zeta", "extra3", "extra4"],
    }
    traj = []
    cycle = 0
    for stim in stims:
        for rep in range(n_repeated_pairs):
            concepts = list(base_concepts[stim])
            # Drift: replace last `concept_drift` items with different ones
            for d in range(concept_drift):
                concepts[-1 - d] = f"drift_{stim}_{rep}_{d}"
            walk = list(reversed(concepts))  # walker visits in some order
            # Build composites = p_identity × small_prime (so divisibility holds
            # by construction; small_prime stands in for p_thermo × stamp)
            chain = []
            for c in walk:
                p_id = _identity_prime_naive(c)
                if force_factorization_violation:
                    chain.append(p_id + 1)  # off-by-one to break divisibility
                else:
                    chain.append(p_id * 7)  # 7 is a stand-in p_thermo × stamp
            traj.append({
                "cycle_index": cycle,
                "stimulus": stim,
                "concepts": concepts,
                "trajectory_walk": walk,
                "prime_chain": chain,
                "prime_identity_coverage": {
                    "concepts_registered": len(concepts),
                    "total_concepts": len(concepts),
                    "coverage_ratio": 1.0,
                },
            })
            cycle += 1
    out = tmp_path / "synth.json"
    out.write_text(json.dumps({"kimera_commit": "synth", "trajectory": traj}))
    return out


def test_constructor_validates_path(tmp_path):
    with pytest.raises(FileNotFoundError):
        PrimeStructureScenario(trajectory_path=str(tmp_path / "missing.json"))


def test_constructor_validates_thresholds(tmp_path):
    p = _make_trajectory(tmp_path)
    with pytest.raises(ValueError, match="recognition_jaccard_floor"):
        PrimeStructureScenario(trajectory_path=str(p),
                               recognition_jaccard_floor=0.0)
    with pytest.raises(ValueError, match="coverage_ratio_floor"):
        PrimeStructureScenario(trajectory_path=str(p),
                               coverage_ratio_floor=1.5)


def test_score_unreachable(tmp_path):
    p = _make_trajectory(tmp_path)
    s = PrimeStructureScenario(trajectory_path=str(p))
    with pytest.raises(NotImplementedError):
        s.score([], [])


def test_perfect_recognition_validates(tmp_path):
    """Same concepts on every repeat → Jaccard = 1.0 → VALIDATED."""
    p = _make_trajectory(tmp_path, n_repeated_pairs=5, concept_drift=0)
    s = PrimeStructureScenario(trajectory_path=str(p),
                               recognition_jaccard_floor=0.9)
    proof = s.run()
    assert proof.verdict.outcome == VALIDATED
    assert proof.verdict.observed_value == 1.0
    detail = proof.evidence[0].detail
    assert detail["recognition_floor"] == 1.0
    assert detail["recognition_mean"] == 1.0


def test_concept_drift_lowers_recognition_floor(tmp_path):
    """Drifted concepts → lower Jaccard."""
    p = _make_trajectory(tmp_path, n_repeated_pairs=5, concept_drift=2)
    s = PrimeStructureScenario(trajectory_path=str(p),
                               recognition_jaccard_floor=0.5)
    proof = s.run()
    detail = proof.evidence[0].detail
    # With 2 drifted positions out of 5, intersection is at most 3, union at
    # most 7 (3 shared + 2 drifted in each side, where drifts are unique per
    # rep) → Jaccard ≈ 3/7 ≈ 0.43 — should be REFUTED at floor=0.5
    assert detail["recognition_floor"] < 1.0


def test_composite_jaccard_zero_for_unique_chains(tmp_path):
    """When prime_chains are unique (different stamps), composite Jaccard is 0."""
    # Build a trajectory where the same stimulus has UNIQUE prime_chains
    # across reps (simulates per-cycle stamp evolution)
    traj = []
    for rep in range(5):
        traj.append({
            "cycle_index": rep,
            "stimulus": "alpha beta",
            "concepts": ["alpha", "beta"],
            "trajectory_walk": ["alpha", "beta"],
            "prime_chain": [1000003 + rep, 2000003 + rep],  # all unique
            "prime_identity_coverage": {"coverage_ratio": 1.0,
                                         "concepts_registered": 2,
                                         "total_concepts": 2},
        })
    p = tmp_path / "uniq_chains.json"
    p.write_text(json.dumps({"kimera_commit": "x", "trajectory": traj}))
    s = PrimeStructureScenario(trajectory_path=str(p),
                               recognition_jaccard_floor=0.5)
    proof = s.run()
    detail = proof.evidence[0].detail
    # concept-Jaccard = 1.0 (same concepts), composite-Jaccard = 0.0 (unique)
    assert detail["recognition_floor"] == 1.0
    assert detail["composite_floor"] == 0.0


def test_f11_composite_factorization_integrity(tmp_path):
    """When chains are p_identity * 7, divisibility by p_identity must = 1.0."""
    p = _make_trajectory(tmp_path, n_repeated_pairs=3,
                         force_factorization_violation=False)
    s = PrimeStructureScenario(trajectory_path=str(p))
    proof = s.run()
    f11 = proof.evidence[0].detail["f11_composite_factorization"]
    assert f11["divisibility_rate"] == 1.0
    assert f11["n_cycles_with_misses"] == 0


def test_f11_violation_surfaces_in_detail(tmp_path):
    """Forced off-by-one composites → F.1.1 divisibility < 1.0."""
    p = _make_trajectory(tmp_path, n_repeated_pairs=3,
                         force_factorization_violation=True)
    s = PrimeStructureScenario(trajectory_path=str(p))
    proof = s.run()
    f11 = proof.evidence[0].detail["f11_composite_factorization"]
    assert f11["divisibility_rate"] == 0.0
    assert f11["n_cycles_with_misses"] >= 1


def test_identity_prime_helper_matches_kimera_substrate():
    """The re-implemented _identity_prime must produce primes per CLAUDE.md.

    CLAUDE.md F.1.1: 'p_identity is SHA-256 hash of canonical concept name → prime'.
    Sanity-check: result is always prime, in [100, 49100+]"""
    for name in ["memory", "structure", "data", "phi", "alexandria", ""]:
        p = _identity_prime_from_canonical(name)
        assert _is_prime(p), f"{name!r} produced non-prime {p}"
        assert 100 <= p, f"{name!r} produced p={p} below floor 100"
        # search-up may exceed 49100 by a few; but rarely > 50000
        assert p < 60000, f"{name!r} produced p={p} surprisingly large"


def test_identity_prime_deterministic():
    """Same name → same prime, always."""
    a = _identity_prime_from_canonical("memory")
    b = _identity_prime_from_canonical("memory")
    assert a == b


def test_signed_proof_carries_provenance(tmp_path):
    p = _make_trajectory(tmp_path)
    s = PrimeStructureScenario(trajectory_path=str(p))
    proof = s.run()
    assert proof.signature
    agents = proof.provenance.get("agent", {})
    assert "ophamin:kimera-swm" in agents
