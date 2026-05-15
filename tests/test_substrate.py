"""Tests for the substrate layer — CycleResult extraction, MockSubstrate, and
the KimeraAdapter batch runner's incremental-emit reconstruction."""

import json
from pathlib import Path

import pytest

from ophamin.seeing.substrate.base import CycleResult
from ophamin.seeing.substrate.kimera_adapter import KimeraAdapter
from ophamin.seeing.substrate.mock import MockSubstrate


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


# -- KimeraAdapter batch runner — incremental-emit reconstruction -----------

def _fake_kimera_repo(tmp_path: Path) -> Path:
    """The minimal directory shape KimeraAdapter.__init__ validates."""
    (tmp_path / "kimera_swm").mkdir()
    venv_python = tmp_path / ".venv" / "bin" / "python"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text("#!/bin/sh\n")  # presence is all __init__ checks
    return tmp_path


def test_kimera_adapter_batch_salvages_completed_cycles_on_timeout(tmp_path):
    """A timeout must NOT discard the batch — run_batch reconstructs from the
    incremental JSONL sink: completed cycles are real CycleResults, the
    unreached tail (and any half-written final line) is adapter_error."""
    adapter = KimeraAdapter(_fake_kimera_repo(tmp_path), mode="batch")

    def fake_invoke(payload, *, probe=False, batch=False, timeout=None):
        # simulate a runner that completed cycles 0..2, then was SIGKILLed
        # mid-write of cycle 3 — and the call itself returns a timeout.
        with open(payload["results_path"], "w") as fh:
            for i in range(3):
                fh.write(json.dumps({
                    "cycle_index": i, "ok": True,
                    "raw": {"verdict": f"cycle-{i}"},
                    "success": True, "halt_mode": "commit",
                    "cycle_seconds": 0.01,
                }) + "\n")
            fh.write('{"cycle_index": 3, "ok": tru')  # half-written line
        return {"ok": False, "stage": "timeout", "error": "batch timed out"}

    adapter._invoke = fake_invoke
    results = adapter.run_batch([f"stimulus {i}" for i in range(6)])

    assert len(results) == 6
    real = [r for r in results if r.halt_mode != "adapter_error"]
    errs = [r for r in results if r.halt_mode == "adapter_error"]
    assert [r.cycle_index for r in real] == [0, 1, 2]  # the salvaged prefix
    assert all(r.raw.get("verdict") == f"cycle-{r.cycle_index}" for r in real)
    assert [r.cycle_index for r in errs] == [3, 4, 5]  # unreached tail + half-written
    assert all(r.error for r in errs)


def test_kimera_adapter_batch_happy_path_uses_stdout_batch(tmp_path):
    """When the runner returns a clean stdout batch, run_batch uses it directly."""
    adapter = KimeraAdapter(_fake_kimera_repo(tmp_path), mode="batch")

    def fake_invoke(payload, *, probe=False, batch=False, timeout=None):
        return {
            "ok": True,
            "construct_seconds": 0.1,
            "batch": [
                {"cycle_index": i, "ok": True, "raw": {"v": i},
                 "success": True, "halt_mode": "commit", "cycle_seconds": 0.01}
                for i in range(4)
            ],
        }

    adapter._invoke = fake_invoke
    results = adapter.run_batch([f"s{i}" for i in range(4)])
    assert len(results) == 4
    assert all(r.success and r.halt_mode != "adapter_error" for r in results)
    assert [r.raw["v"] for r in results] == [0, 1, 2, 3]


def test_kimera_adapter_propagates_cycle_seconds_into_raw(tmp_path):
    """Regression: the subprocess runner emits ``cycle_seconds`` at the entry
    TOP level (alongside ``raw``). The parent-side reconstruction must surface
    it INTO raw so downstream consumers (the ThroughputCeiling engineering-
    tier scenario, the InstrumentedSubstrate's per-cycle wall-time
    attribution) see real per-cycle wall-times instead of falling back to
    batch-averaged estimates.

    Pre-fix this caused 0/200 measurements on a real 200-cycle live run
    despite cycles running; the engineering-tier scenario's INCONCLUSIVE
    verdict was the symptom that surfaced the bug. Fix landed 2026-05-15.
    """
    adapter = KimeraAdapter(_fake_kimera_repo(tmp_path), mode="batch")

    def fake_invoke(payload, *, probe=False, batch=False, timeout=None):
        return {
            "ok": True,
            "construct_seconds": 0.1,
            "batch": [
                {
                    "cycle_index": i, "ok": True,
                    "raw": {"some_field": "kept"},
                    "success": True, "halt_mode": "commit",
                    "cycle_seconds": 1.23 + i,   # the field at risk
                }
                for i in range(3)
            ],
        }

    adapter._invoke = fake_invoke
    results = adapter.run_batch([f"s{i}" for i in range(3)])
    assert len(results) == 3
    # cycle_seconds MUST be present inside raw on every cycle
    for i, r in enumerate(results):
        assert "cycle_seconds" in r.raw, f"cycle {i}: cycle_seconds missing from raw"
        assert r.raw["cycle_seconds"] == pytest.approx(1.23 + i)
    # the inner raw field still survives the merge
    assert all(r.raw["some_field"] == "kept" for r in results)


def test_kimera_adapter_preserves_explicit_raw_cycle_seconds(tmp_path):
    """If the substrate itself puts cycle_seconds INTO raw (synthetic future
    case where Kimera emits it natively), the parent must NOT overwrite it
    with the entry top-level value."""
    adapter = KimeraAdapter(_fake_kimera_repo(tmp_path), mode="batch")

    def fake_invoke(payload, *, probe=False, batch=False, timeout=None):
        return {
            "ok": True,
            "construct_seconds": 0.1,
            "batch": [
                {
                    "cycle_index": 0, "ok": True,
                    "raw": {"cycle_seconds": 99.9},  # explicit in raw
                    "success": True, "halt_mode": "commit",
                    "cycle_seconds": 1.0,             # entry-level
                },
            ],
        }

    adapter._invoke = fake_invoke
    results = adapter.run_batch(["x"])
    assert len(results) == 1
    # raw's explicit value WINS — the entry-level value does not overwrite it
    assert results[0].raw["cycle_seconds"] == pytest.approx(99.9)
