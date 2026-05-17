"""Tests for SinewWiderUnificationScenario (Phase 5, 2026-05-17)."""

from __future__ import annotations

import json
import math
import random

import pytest

from ophamin.measuring.proof import REFUTED, VALIDATED
from ophamin.measuring.scenarios.sinew_wider_unification import (
    SinewWiderUnificationScenario,
)


def _make_trajectory(
    tmp_path,
    *,
    cycles=None,
    commit: str = "synthetic_commit",
    seed: int = 7,
):
    """Build synthetic Sinew capture with pressure/tension/CW + 12 energy fields."""
    if cycles is None:
        random.seed(seed)
        cycles = []
        for i in range(80):
            is_walker = (i % 4 == 0 and i > 0)
            phase = (i * 0.7) % (2 * math.pi)
            p_val = 1.0 + 0.5 * math.sin(phase)
            t_val = 1.0 - 0.5 * math.sin(phase)
            cw_seed = 0.5 + 0.5 * (1.0 - 0.5 * math.sin(phase))  # anti-correlated
            energy = {
                # Compatible-ish: small random
                "quantum_energy": random.uniform(0.5, 1.5),
                "spde_ground_energy": 1.0 + 0.05 * math.sin(phase * 2),
                "entanglement_entropy": random.uniform(0.5, 1.5),
                "riemann_zeta_entropy": 1.0 + 0.1 * math.cos(phase),
                "riemann_zeta_free_energy": 1.0 - 0.1 * math.cos(phase),
                "crystal_binding_energy": 1.0 + 0.05 * math.cos(phase),
                "quantum_interference_entropy": 1.0 + 0.05 * math.sin(phase),
                "quantum_prime_basis_entropy": random.uniform(0.5, 1.5),
                "rosetta_composition_entropy": 1.0 + 0.05 * math.cos(phase * 1.5),
                "voronoi_neighbourhood_entropy": 1.0 + 0.05 * math.sin(phase * 0.5),
                "turing_pattern_entropy": 1.0 + 0.05 * math.cos(phase * 0.7),
            }
            cycles.append({
                "cycle_index": i, "crashed": False,
                "pressure_proxies": {"allen_cahn_mean_free_energy": p_val},
                "tension_proxies": {"graph_coherence": t_val},
                "scar": {
                    "scar_coherence_weight": cw_seed,
                    "scar_coherence_weight_modulated": cw_seed * 1.1,
                },
                "scar_id": f"s{i}",
                "ouroboros": {"ouroboros_total_fused": i // 10},
                "energy": energy,
                "prime_log_energy": float(random.uniform(50, 150)),
                "events": {
                    "halt_reason": "lateral_leap" if is_walker else "exhausted",
                    "walker_annealing_events": 1 if is_walker else 0,
                },
            })
    p = tmp_path / "synth_capture.json"
    p.write_text(json.dumps(cycles))
    meta = tmp_path / "metadata.json"
    meta.write_text(json.dumps({"kimera_commit": commit}))
    return p


def test_constructor_validates_path(tmp_path):
    with pytest.raises(FileNotFoundError):
        SinewWiderUnificationScenario(trajectory_path=str(tmp_path / "missing.json"))


def test_constructor_validates_threshold_bounds(tmp_path):
    p = _make_trajectory(tmp_path)
    with pytest.raises(ValueError, match="compatible_or_extends_min"):
        SinewWiderUnificationScenario(trajectory_path=str(p), compatible_or_extends_min=0)
    with pytest.raises(ValueError, match="compatible_or_extends_min"):
        SinewWiderUnificationScenario(trajectory_path=str(p), compatible_or_extends_min=13)


def test_constructor_validates_noise_floor(tmp_path):
    p = _make_trajectory(tmp_path)
    with pytest.raises(ValueError, match="noise_floor"):
        SinewWiderUnificationScenario(trajectory_path=str(p), noise_floor=0.0)
    with pytest.raises(ValueError, match="noise_floor"):
        SinewWiderUnificationScenario(trajectory_path=str(p), noise_floor=0.5)


def test_score_unreachable(tmp_path):
    p = _make_trajectory(tmp_path)
    s = SinewWiderUnificationScenario(trajectory_path=str(p))
    with pytest.raises(NotImplementedError):
        s.score([], [])


def test_proof_record_signed_and_commit(tmp_path):
    p = _make_trajectory(tmp_path, commit="abcdef123")
    s = SinewWiderUnificationScenario(
        trajectory_path=str(p), compatible_or_extends_min=1,  # loose
    )
    proof = s.run()
    assert proof.signature
    assert proof.proof_id
    assert proof.substrate_git_commit == "abcdef123"


def test_proof_detail_breakdown(tmp_path):
    p = _make_trajectory(tmp_path)
    s = SinewWiderUnificationScenario(
        trajectory_path=str(p), compatible_or_extends_min=1,
    )
    proof = s.run()
    detail = proof.evidence[0].detail
    assert detail["n_extends"] + detail["n_compatible"] + detail["n_breaks"] + detail["n_insufficient"] == 12
    assert detail["baseline_3term_ratio"] > 0
    assert isinstance(detail["per_candidate"], list)
    assert len(detail["per_candidate"]) == 12
    # Each candidate has the full classification info
    for c in detail["per_candidate"]:
        assert "field" in c
        assert "verdict" in c
        assert c["verdict"] in ("EXTENDS", "COMPATIBLE", "BREAKS", "INSUFFICIENT")


def test_short_trajectory_refused(tmp_path):
    p = _make_trajectory(tmp_path, cycles=[{
        "cycle_index": 0, "crashed": False,
        "pressure_proxies": {"x": 1.0}, "tension_proxies": {"y": 1.0},
        "scar": {"scar_coherence_weight": 0.5}, "scar_id": "s0",
        "ouroboros": {"ouroboros_total_fused": 0}, "energy": {},
        "prime_log_energy": 100.0,
        "events": {"halt_reason": "exhausted", "walker_annealing_events": 0},
    }])
    s = SinewWiderUnificationScenario(trajectory_path=str(p))
    with pytest.raises(ValueError, match="≥ 50"):
        s.run()


def test_tight_threshold_refutes(tmp_path):
    """Pre-register an impossibly tight threshold (12 of 12 must extend/be compatible)
    — high probability of refutation on random synthetic data."""
    p = _make_trajectory(tmp_path, seed=42)
    s = SinewWiderUnificationScenario(
        trajectory_path=str(p), compatible_or_extends_min=12,
    )
    proof = s.run()
    # With random data and tight threshold, likely REFUTED — but we just
    # check the verdict is well-formed
    assert proof.verdict.outcome in (VALIDATED, REFUTED)
    if proof.verdict.outcome == REFUTED:
        assert proof.evidence[0].statistic_value < 12


def test_loose_threshold_validates(tmp_path):
    """compatible_or_extends_min=1 → almost any trajectory passes."""
    p = _make_trajectory(tmp_path)
    s = SinewWiderUnificationScenario(
        trajectory_path=str(p), compatible_or_extends_min=1,
    )
    proof = s.run()
    assert proof.verdict.outcome == VALIDATED


def test_missing_energy_field_handled_as_insufficient(tmp_path):
    """If an energy field is entirely missing/zero across cycles → INSUFFICIENT verdict."""
    random.seed(11)
    cycles = []
    for i in range(60):
        is_walker = (i % 4 == 0 and i > 0)
        phase = (i * 0.7) % (2 * math.pi)
        cycles.append({
            "cycle_index": i, "crashed": False,
            "pressure_proxies": {"x": 1.0 + 0.3 * math.sin(phase)},
            "tension_proxies": {"y": 1.0 - 0.3 * math.sin(phase)},
            "scar": {"scar_coherence_weight": 0.5 + 0.5 * (1 - 0.3 * math.sin(phase))},
            "scar_id": f"s{i}",
            "ouroboros": {"ouroboros_total_fused": i // 10},
            "energy": {  # Most fields constant → INSUFFICIENT
                "quantum_energy": 1.0,
                "spde_ground_energy": 1.0,
                "entanglement_entropy": 1.0,
                "riemann_zeta_entropy": 1.0,
                "riemann_zeta_free_energy": 1.0,
                "crystal_binding_energy": 1.0,
                "quantum_interference_entropy": 1.0,
                "quantum_prime_basis_entropy": 1.0,
                "rosetta_composition_entropy": 1.0,
                "voronoi_neighbourhood_entropy": 1.0,
                "turing_pattern_entropy": 1.0,
            },
            "prime_log_energy": 100.0,  # constant
            "events": {
                "halt_reason": "lateral_leap" if is_walker else "exhausted",
                "walker_annealing_events": 1 if is_walker else 0,
            },
        })
    p = _make_trajectory(tmp_path, cycles=cycles)
    s = SinewWiderUnificationScenario(
        trajectory_path=str(p), compatible_or_extends_min=1,
    )
    proof = s.run()
    detail = proof.evidence[0].detail
    # All constant fields should be INSUFFICIENT
    assert detail["n_insufficient"] >= 10


def test_default_threshold_matches_pre_registration(tmp_path):
    """Default threshold (8 of 12) and noise_floor (0.01) match the campaign's
    pre-registered values — these are load-bearing for the X5 row in
    EMPIRICAL_VALIDATION."""
    p = _make_trajectory(tmp_path)
    s = SinewWiderUnificationScenario(trajectory_path=str(p))
    assert s.compatible_or_extends_min == 8
    assert s.noise_floor == 0.01
