"""Tests for SinewModulationDisruptionScenario (Round N, 2026-05-17)."""

from __future__ import annotations

import json
import math
import random

import pytest

from ophamin.measuring.proof import REFUTED, VALIDATED
from ophamin.measuring.scenarios.sinew_modulation_disruption import (
    SinewModulationDisruptionScenario,
)


def _make_trajectory(
    tmp_path,
    *,
    cycles: list[dict] | None = None,
    commit: str = "synthetic_commit_sha",
):
    """Build synthetic Sinew capture with BOTH CW fields."""
    if cycles is None:
        cycles = []
        # 60 cycles with: seed CW conserved (anti-correlated with P+T),
        # modulated CW NOT conserved (random noise)
        random.seed(7)
        for i in range(60):
            is_walker = (i % 4 == 0 and i > 0)
            phase = (i * 0.7) % (2 * math.pi)
            p_val = 1.0 + 0.5 * math.sin(phase)
            t_val = 1.0 - 0.5 * math.sin(phase)
            cw_seed = 0.5 + 0.5 * (1.0 - 0.5 * math.sin(phase))  # anti-correlated
            cw_mod = random.uniform(0.3, 1.4)  # uncorrelated → disrupts conservation
            cycles.append({
                "cycle_index": i, "crashed": False,
                "pressure_proxies": {"allen_cahn_mean_free_energy": p_val},
                "tension_proxies": {"graph_coherence": t_val},
                "scar": {
                    "scar_coherence_weight": cw_seed,
                    "scar_coherence_weight_modulated": cw_mod,
                },
                "scar_id": f"s{i}",
                "ouroboros": {"ouroboros_total_fused": i // 10},
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
        SinewModulationDisruptionScenario(trajectory_path=str(tmp_path / "missing.json"))


def test_constructor_validates_threshold_bounds(tmp_path):
    p = _make_trajectory(tmp_path)
    with pytest.raises(ValueError, match="disruption_delta_min"):
        SinewModulationDisruptionScenario(trajectory_path=str(p), disruption_delta_min=0.0)
    with pytest.raises(ValueError, match="disruption_delta_min"):
        SinewModulationDisruptionScenario(trajectory_path=str(p), disruption_delta_min=1.0)


def test_score_unreachable(tmp_path):
    p = _make_trajectory(tmp_path)
    s = SinewModulationDisruptionScenario(trajectory_path=str(p))
    with pytest.raises(NotImplementedError):
        s.score([], [])


def test_disrupted_trajectory_validates(tmp_path):
    """Random modulated CW vs anti-correlated seed CW → mod > seed → VALIDATED."""
    p = _make_trajectory(tmp_path)
    s = SinewModulationDisruptionScenario(
        trajectory_path=str(p), disruption_delta_min=0.05,
    )
    proof = s.run()
    assert proof.verdict.outcome == VALIDATED
    assert proof.evidence[0].statistic_value > 0  # delta is positive


def test_missing_modulated_field_loud_fail(tmp_path):
    """If scar_coherence_weight_modulated absent from trajectory → loud fail."""
    cycles = []
    for i in range(60):
        cycles.append({
            "cycle_index": i, "crashed": False,
            "pressure_proxies": {"x": 1.0},
            "tension_proxies": {"y": 1.0},
            "scar": {"scar_coherence_weight": 0.5},  # NO modulated field
            "scar_id": f"s{i}",
            "ouroboros": {"ouroboros_total_fused": 0},
            "energy": {},
            "events": {
                "halt_reason": "lateral_leap" if (i % 4 == 0 and i > 0) else "exhausted",
                "walker_annealing_events": 1 if (i % 4 == 0 and i > 0) else 0,
            },
        })
    p = _make_trajectory(tmp_path, cycles=cycles)
    s = SinewModulationDisruptionScenario(trajectory_path=str(p), disruption_delta_min=0.05)
    with pytest.raises(ValueError, match="scar_coherence_weight_modulated"):
        s.run()


def test_identical_cw_refutes(tmp_path):
    """If modulated == seed → delta=0 → REFUTED at any positive threshold."""
    cycles = []
    random.seed(13)
    for i in range(60):
        is_walker = (i % 4 == 0 and i > 0)
        phase = (i * 0.7) % (2 * math.pi)
        cw = 0.5 + 0.5 * (1.0 - 0.5 * math.sin(phase))
        cycles.append({
            "cycle_index": i, "crashed": False,
            "pressure_proxies": {"x": 1.0 + 0.5 * math.sin(phase)},
            "tension_proxies": {"y": 1.0 - 0.5 * math.sin(phase)},
            "scar": {
                "scar_coherence_weight": cw,
                "scar_coherence_weight_modulated": cw,  # identical
            },
            "scar_id": f"s{i}",
            "ouroboros": {"ouroboros_total_fused": i // 10},
            "energy": {},
            "events": {
                "halt_reason": "lateral_leap" if is_walker else "exhausted",
                "walker_annealing_events": 1 if is_walker else 0,
            },
        })
    p = _make_trajectory(tmp_path, cycles=cycles)
    s = SinewModulationDisruptionScenario(
        trajectory_path=str(p), disruption_delta_min=0.05,
    )
    # When modulated == seed in raw values, normalization makes them identical,
    # so delta will be 0 or near-0 → REFUTED at threshold 0.05
    proof = s.run()
    assert proof.verdict.outcome == REFUTED
    assert abs(proof.evidence[0].statistic_value) < 0.05


def test_proof_record_carries_commit_hash(tmp_path):
    p = _make_trajectory(tmp_path, commit="xyz789")
    s = SinewModulationDisruptionScenario(
        trajectory_path=str(p), disruption_delta_min=0.05,
    )
    proof = s.run()
    assert proof.substrate_git_commit == "xyz789"


def test_proof_record_signed(tmp_path):
    p = _make_trajectory(tmp_path)
    s = SinewModulationDisruptionScenario(
        trajectory_path=str(p), disruption_delta_min=0.05,
    )
    proof = s.run()
    assert proof.signature
    assert proof.proof_id


def test_proof_includes_counter_compensation_correlation(tmp_path):
    p = _make_trajectory(tmp_path)
    s = SinewModulationDisruptionScenario(
        trajectory_path=str(p), disruption_delta_min=0.05,
    )
    proof = s.run()
    detail = proof.evidence[0].detail
    assert "counter_compensation_cor" in detail
    # Distribution stats present
    assert "cw_distribution" in detail
    cwd = detail["cw_distribution"]
    assert all(k in cwd for k in ("seed_min", "seed_max", "modulated_min", "modulated_max"))


def test_short_trajectory_refused(tmp_path):
    p = _make_trajectory(tmp_path, cycles=[{
        "cycle_index": 0, "crashed": False,
        "pressure_proxies": {"x": 1.0}, "tension_proxies": {"y": 1.0},
        "scar": {
            "scar_coherence_weight": 0.5,
            "scar_coherence_weight_modulated": 0.8,
        }, "scar_id": "s0",
        "ouroboros": {"ouroboros_total_fused": 0}, "energy": {},
        "events": {"halt_reason": "exhausted", "walker_annealing_events": 0},
    }])
    s = SinewModulationDisruptionScenario(
        trajectory_path=str(p), disruption_delta_min=0.05,
    )
    with pytest.raises(ValueError, match="≥ 50"):
        s.run()
