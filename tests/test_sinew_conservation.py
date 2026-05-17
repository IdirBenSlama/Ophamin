"""Tests for SinewConservationScenario (Round N, 2026-05-17).

Synthetic-trajectory-driven tests verify the scenario's contract:
- VALIDATES when walker_m4 conservation ratio < threshold
- REFUTES when walker_m4 conservation ratio >= threshold
- Loud failures on missing path, bad threshold, empty trajectory, too few events
- Proof record includes commit hash, signed signature, secondary characterizations
"""

from __future__ import annotations

import json

import pytest

from ophamin.measuring.proof import REFUTED, VALIDATED
from ophamin.measuring.scenarios.sinew_conservation import SinewConservationScenario


def _make_trajectory(
    tmp_path,
    *,
    cycles: list[dict] | None = None,
    commit: str = "synthetic_commit_sha",
):
    """Build synthetic Sinew capture (list-of-dicts format)."""
    if cycles is None:
        # 60 cycles, ~15 walker_m4 events, with controlled conservation
        cycles = []
        for i in range(60):
            # Inject walker_m4 every 4th cycle
            is_walker = (i % 4 == 0 and i > 0)
            # Inject ouroboros every 10th
            is_ouro = (i % 10 == 0 and i > 0)
            # Vary pressure / tension / CW so (P+T+CW) is approximately conserved
            # at walker_m4 events
            phase = (i * 0.7) % (2 * 3.14159)
            import math as _m
            p_val = 1.0 + 0.3 * _m.sin(phase)
            t_val = 1.0 - 0.3 * _m.sin(phase)
            cw_val = 0.5 + 0.5 * (1.0 - 0.3 * _m.sin(phase))  # anti-correlated with P+T
            cycles.append({
                "cycle_index": i,
                "crashed": False,
                "pressure_proxies": {"allen_cahn_mean_free_energy": p_val},
                "tension_proxies": {"graph_coherence": t_val},
                "scar": {
                    "scar_coherence_weight": cw_val,
                    "scar_coherence_weight_modulated": cw_val * 1.1,
                },
                "scar_id": f"s{i}",
                "ouroboros": {"ouroboros_total_fused": (i // 10)},
                "energy": {},
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
        SinewConservationScenario(trajectory_path=str(tmp_path / "missing.json"))


def test_constructor_validates_threshold_bounds(tmp_path):
    p = _make_trajectory(tmp_path)
    with pytest.raises(ValueError, match="conservation_ratio_max"):
        SinewConservationScenario(trajectory_path=str(p), conservation_ratio_max=0.0)
    with pytest.raises(ValueError, match="conservation_ratio_max"):
        SinewConservationScenario(trajectory_path=str(p), conservation_ratio_max=1.0)


def test_score_unreachable(tmp_path):
    """score() raises — scenario uses custom run() loop."""
    p = _make_trajectory(tmp_path)
    s = SinewConservationScenario(trajectory_path=str(p))
    with pytest.raises(NotImplementedError):
        s.score([], [])


def test_synthetic_conserved_trajectory_validates(tmp_path):
    """Anti-correlated CW vs P+T → conservation holds → VALIDATED."""
    p = _make_trajectory(tmp_path)
    s = SinewConservationScenario(
        trajectory_path=str(p), conservation_ratio_max=0.30,  # loose for synthetic
    )
    proof = s.run()
    assert proof.verdict.outcome == VALIDATED


def test_proof_record_carries_commit_hash(tmp_path):
    p = _make_trajectory(tmp_path, commit="abc123def456")
    s = SinewConservationScenario(
        trajectory_path=str(p), conservation_ratio_max=0.30,
    )
    proof = s.run()
    assert proof.substrate_git_commit == "abc123def456"


def test_proof_record_signed(tmp_path):
    p = _make_trajectory(tmp_path)
    s = SinewConservationScenario(
        trajectory_path=str(p), conservation_ratio_max=0.30,
    )
    proof = s.run()
    assert proof.signature  # non-empty signature
    assert proof.proof_id  # content-addressed id present


def test_proof_includes_walker_m4_ouroboros_scar_breakdown(tmp_path):
    p = _make_trajectory(tmp_path)
    s = SinewConservationScenario(
        trajectory_path=str(p), conservation_ratio_max=0.30,
    )
    proof = s.run()
    detail = proof.evidence[0].detail
    assert "walker_m4_ratio" in detail
    assert "ouroboros_ratio" in detail
    assert "scar_ratio" in detail
    assert "scar_magnitude_quartiles" in detail
    # Quartile structure present
    qs = detail["scar_magnitude_quartiles"]
    assert isinstance(qs, dict)


def test_short_trajectory_refused(tmp_path):
    """< 50 cycles refused — too few events for verdict."""
    p = _make_trajectory(tmp_path, cycles=[{
        "cycle_index": 0, "crashed": False,
        "pressure_proxies": {"x": 1.0}, "tension_proxies": {"y": 1.0},
        "scar": {"scar_coherence_weight": 0.5}, "scar_id": "s0",
        "ouroboros": {"ouroboros_total_fused": 0}, "energy": {},
        "events": {"halt_reason": "exhausted", "walker_annealing_events": 0},
    }])
    s = SinewConservationScenario(trajectory_path=str(p), conservation_ratio_max=0.10)
    with pytest.raises(ValueError, match="≥ 50"):
        s.run()


def test_no_walker_m4_events_refused(tmp_path):
    """If trajectory has no walker_m4 events, scenario refuses verdict."""
    cycles = []
    for i in range(60):
        cycles.append({
            "cycle_index": i, "crashed": False,
            "pressure_proxies": {"x": 1.0 + i*0.01},
            "tension_proxies": {"y": 1.0 + i*0.01},
            "scar": {"scar_coherence_weight": 0.5},
            "scar_id": f"s{i}",
            "ouroboros": {"ouroboros_total_fused": 0},
            "energy": {},
            "events": {"halt_reason": "exhausted", "walker_annealing_events": 0},
        })
    p = _make_trajectory(tmp_path, cycles=cycles)
    s = SinewConservationScenario(trajectory_path=str(p), conservation_ratio_max=0.10)
    with pytest.raises(ValueError, match="too low"):
        s.run()


def test_disrupted_trajectory_refutes(tmp_path):
    """Random P/T/CW (no compensation structure) → ratio high → REFUTED at tight threshold."""
    import random
    random.seed(42)
    cycles = []
    for i in range(60):
        is_walker = (i % 4 == 0 and i > 0)
        cycles.append({
            "cycle_index": i, "crashed": False,
            "pressure_proxies": {"allen_cahn_mean_free_energy": random.uniform(0.5, 2.5)},
            "tension_proxies": {"graph_coherence": random.uniform(0.5, 2.5)},
            "scar": {"scar_coherence_weight": random.uniform(0.5, 1.0)},
            "scar_id": f"s{i}",
            "ouroboros": {"ouroboros_total_fused": i // 10},
            "energy": {},
            "events": {
                "halt_reason": "lateral_leap" if is_walker else "exhausted",
                "walker_annealing_events": 1 if is_walker else 0,
            },
        })
    p = _make_trajectory(tmp_path, cycles=cycles)
    s = SinewConservationScenario(trajectory_path=str(p), conservation_ratio_max=0.05)  # tight
    proof = s.run()
    # The random trajectory should fail tight threshold
    assert proof.verdict.outcome == REFUTED
