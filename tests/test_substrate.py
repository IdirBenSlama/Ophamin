"""Tests for the substrate layer — CycleResult extraction and MockSubstrate."""

from ophamin.substrate.base import CycleResult
from ophamin.substrate.mock import MockSubstrate


def test_cycle_result_default_metric_extraction():
    result = CycleResult(
        cycle_index=1,
        success=True,
        raw={
            "total_cycles": 5,
            "request_latency_ms": 12.0,
            "drift_score": 0.3,
            "phi": 0.7,
            "jaccard_overlap": 0.4,
        },
    )
    bundle = result.to_metric_bundle()
    assert bundle.tier1.counters["total_cycles"] == 5.0
    assert bundle.tier1.timers["request_latency_ms"] == [12.0]
    assert bundle.tier2.drift_score == 0.3
    assert bundle.tier3.prime_deformation_delta == 0.7
    assert bundle.tier3.jaccard_overlap == 0.4


def test_mock_substrate_is_deterministic_under_seed():
    a = MockSubstrate(seed=123)
    b = MockSubstrate(seed=123)
    phis_a = [a.run_cycle("s").raw["phi"] for _ in range(20)]
    phis_b = [b.run_cycle("s").raw["phi"] for _ in range(20)]
    assert phis_a == phis_b


def test_mock_substrate_reset_restores_sequence():
    sut = MockSubstrate(seed=7)
    first = [sut.run_cycle("s").raw["phi"] for _ in range(10)]
    sut.reset()
    second = [sut.run_cycle("s").raw["phi"] for _ in range(10)]
    assert first == second


def test_mock_substrate_run_cycle_shape():
    sut = MockSubstrate(seed=0)
    result = sut.run_cycle("hello", {"injection_rate": 0.5})
    assert isinstance(result, CycleResult)
    assert result.metric_bundle is not None
    assert result.success is True
    assert result.halt_mode is not None
    assert "phi" in result.raw


def test_mock_substrate_git_commit_stable():
    assert MockSubstrate(seed=42).git_commit() == MockSubstrate(seed=42).git_commit()
    assert MockSubstrate(seed=1).git_commit() != MockSubstrate(seed=2).git_commit()


def test_mock_substrate_collapse_in_collapse_cell_at_low_entropy():
    sut = MockSubstrate(seed=3, collapse_cells=["C_1"], collapse_entropy_below=0.02)
    collapses = 0
    for _ in range(40):
        sut.reset()
        result = sut.run_cycle("s", {"cell": "C_1", "entropy_coefficient": 0.005})
        if not result.success:
            collapses += 1
    # collapse probability is 0.9 inside a collapse cell at low entropy
    assert collapses > 25


def test_mock_substrate_no_collapse_outside_collapse_cell():
    sut = MockSubstrate(seed=3, collapse_cells=["C_1"])
    for _ in range(40):
        sut.reset()
        result = sut.run_cycle("s", {"cell": "C_other", "entropy_coefficient": 0.005})
        assert result.success is True
