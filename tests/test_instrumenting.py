"""Tests for the instrumenting wheel (Phase 1: external psutil profiling).

Exercised without Kimera via MockSubstrate-style fakes that produce
synthetic CycleResults. The Kimera-live smoke is the responsibility of the
example runner.
"""

from __future__ import annotations

import time
from typing import Any

import pytest

from ophamin.instrumenting import (
    BatchResourceProfile,
    CycleResourceProfile,
    InstrumentedSubstrate,
    ResourceWatcher,
)
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest


# --------------------------------------------------------------------------
# A synthetic substrate that emits cycle_seconds in raw (matches Kimera)
# --------------------------------------------------------------------------


class _FakeAdapter(SubstrateUnderTest):
    name = "fake-adapter"

    def __init__(self, per_cycle_sleep_s: float = 0.005) -> None:
        self._sleep = per_cycle_sleep_s
        self._cycle = 0

    def reset(self) -> None:
        self._cycle = 0

    def run_cycle(self, stimulus: Any, params: dict | None = None) -> CycleResult:
        t0 = time.perf_counter()
        time.sleep(self._sleep)
        wall = time.perf_counter() - t0
        self._cycle += 1
        return CycleResult(
            cycle_index=self._cycle - 1,
            success=True,
            raw={"cycle_seconds": wall, "stimulus": str(stimulus)},
            halt_mode="commit",
        )

    def run_batch(self, stimuli: list[Any], params: dict | None = None) -> list[CycleResult]:
        return [self.run_cycle(s, params) for s in stimuli]

    def git_commit(self) -> str:
        return "fake-deadbeef"

    def metadata(self) -> dict[str, Any]:
        return {"name": self.name, "target_class": "fake.target.Class"}


# --------------------------------------------------------------------------
# ResourceWatcher
# --------------------------------------------------------------------------


def test_resource_watcher_brackets_a_batch():
    watcher = ResourceWatcher.for_self()
    watcher.start()
    time.sleep(0.02)
    watcher.stop()
    profile = watcher.build_profile([0.005, 0.005, 0.005, 0.005])
    assert profile.n_cycles == 4
    assert profile.batch_wall_time_s > 0.015  # at least the sleep duration
    assert profile.attribution_kind == "batch_averaged"
    assert len(profile.per_cycle) == 4


def test_resource_watcher_observe_tracks_peak_rss():
    watcher = ResourceWatcher.for_self()
    watcher.start()
    # allocate a chunk to ensure RSS observable; observe() must capture peak
    chunk = bytearray(8 * 1024 * 1024)  # 8 MiB
    watcher.observe()
    chunk.clear()  # release
    watcher.stop()
    # peak should be >= before- and after-bytes (we allocated 8 MiB during the window)
    assert watcher._rss_peak >= watcher._start_sample.rss_bytes


def test_resource_watcher_for_self_takes_a_real_sample():
    watcher = ResourceWatcher.for_self()
    sample = watcher.sample()
    assert sample.rss_bytes > 0
    assert sample.num_threads >= 1
    assert sample.process_count >= 1


def test_resource_watcher_for_nonexistent_pid_returns_zero_sample():
    # PID 999999 is unlikely to exist; should produce a best-effort empty sample
    watcher = ResourceWatcher.for_pid(999999)
    sample = watcher.sample()
    assert sample.rss_bytes == 0
    assert sample.process_count == 0


def test_resource_watcher_build_without_start_raises():
    watcher = ResourceWatcher.for_self()
    with pytest.raises(RuntimeError, match="without matching start"):
        watcher.build_profile([0.1, 0.1])


# --------------------------------------------------------------------------
# Profile shape
# --------------------------------------------------------------------------


def test_batch_profile_to_dict_carries_distributions():
    watcher = ResourceWatcher.for_self()
    watcher.start()
    time.sleep(0.005)
    watcher.stop()
    profile = watcher.build_profile([0.001, 0.002, 0.001, 0.002, 0.001])
    d = profile.to_dict()
    assert "cycle_wall_distribution" in d
    assert "cycle_cpu_distribution" in d
    assert "cycle_rss_distribution" in d
    assert d["cycle_wall_distribution"]["n"] == 5
    assert d["attribution_kind"] == "batch_averaged"
    assert d["batch_cpu_time_total_s"] == pytest.approx(
        d["batch_cpu_time_user_s"] + d["batch_cpu_time_system_s"]
    )
    assert "per_cycle" in d and len(d["per_cycle"]) == 5


def test_cycle_resource_profile_to_dict_round_trips():
    profile = CycleResourceProfile(
        cycle_index=3,
        wall_time_s=0.015,
        cpu_time_attributed_s=0.012,
        rss_peak_bytes_attributed=1024 * 1024 * 64,
        page_faults_attributed=20,
        attribution_kind="batch_averaged",
    )
    d = profile.to_dict()
    assert d["cycle_index"] == 3
    assert d["wall_time_s"] == pytest.approx(0.015)
    assert d["attribution_kind"] == "batch_averaged"


# --------------------------------------------------------------------------
# InstrumentedSubstrate decorator
# --------------------------------------------------------------------------


def test_instrumented_substrate_wraps_fake_adapter():
    inst = InstrumentedSubstrate(_FakeAdapter(per_cycle_sleep_s=0.003))
    assert inst.last_profile() is None
    results = inst.run_batch(["a", "b", "c", "d"])
    assert len(results) == 4
    profile = inst.last_profile()
    assert profile is not None
    assert profile.n_cycles == 4
    # per-cycle wall-times came from cycle_seconds in raw -> sane bounds
    assert all(c.wall_time_s > 0.001 for c in profile.per_cycle)
    assert profile.batch_wall_time_s >= sum(c.wall_time_s for c in profile.per_cycle) * 0.9
    # the attribution kind is honest
    assert profile.attribution_kind == "batch_averaged"


def test_instrumented_substrate_name_surfaces_inner():
    inst = InstrumentedSubstrate(_FakeAdapter())
    assert inst.name == "instrumented(fake-adapter)"
    assert inst.metadata()["instrumented"] is True


def test_instrumented_substrate_rejects_non_substrate_input():
    class _NotASubstrate:
        pass
    with pytest.raises(TypeError, match="SubstrateUnderTest"):
        InstrumentedSubstrate(_NotASubstrate())


def test_instrumented_substrate_falls_back_when_cycle_seconds_missing():
    """If the substrate doesn't populate cycle_seconds, the wrapper still
    produces a profile (evenly-divided estimate)."""
    class _StubAdapter(SubstrateUnderTest):
        name = "stub"
        def reset(self): pass
        def run_cycle(self, s, p=None):
            return CycleResult(0, True, {}, "commit")  # no cycle_seconds
        def run_batch(self, stimuli, p=None):
            time.sleep(0.01)
            return [
                CycleResult(i, True, {}, "commit")  # raw has no cycle_seconds
                for i, _ in enumerate(stimuli)
            ]
        def git_commit(self): return "stub"

    inst = InstrumentedSubstrate(_StubAdapter())
    results = inst.run_batch(["a", "b", "c"])
    profile = inst.last_profile()
    assert profile is not None
    assert profile.n_cycles == 3
    # cycle_seconds absent -> evenly divided estimate, sum approximates batch
    assert all(c.wall_time_s >= 0 for c in profile.per_cycle)
    # in the absence of per-cycle data the cycles get equal time shares
    walls = [c.wall_time_s for c in profile.per_cycle]
    if walls and walls[0] > 0:
        assert max(walls) - min(walls) < 1e-6  # all equal under fallback


def test_instrumented_substrate_reset_passes_through():
    fake = _FakeAdapter()
    inst = InstrumentedSubstrate(fake)
    inst.run_batch(["x"])
    assert fake._cycle == 1
    inst.reset()
    assert fake._cycle == 0


def test_instrumented_substrate_run_cycle_passes_through():
    inst = InstrumentedSubstrate(_FakeAdapter(per_cycle_sleep_s=0.001))
    res = inst.run_cycle("hello")
    assert res.success
    # run_cycle does NOT capture a profile — only run_batch does
    assert inst.last_profile() is None


def test_resource_watcher_observe_returns_a_fresh_sample():
    watcher = ResourceWatcher.for_self()
    watcher.start()
    obs = watcher.observe()
    watcher.stop()
    assert obs.captured_at_perf >= watcher._start_sample.captured_at_perf
    assert obs.rss_bytes > 0


# --------------------------------------------------------------------------
# Periodic subprocess sampler — closes the short-lived-subprocess gap
# --------------------------------------------------------------------------


def test_resource_watcher_periodic_sampling_records_polls():
    """When periodic sampling is on, the profile reports cpu_source as
    'periodic_subprocess_sampler' and at least one poll."""
    watcher = ResourceWatcher.for_self(periodic_sampling=True, poll_interval_s=0.02)
    watcher.start()
    time.sleep(0.1)  # enough to accumulate several polls at 20ms interval
    watcher.stop()
    profile = watcher.build_profile([0.025, 0.025, 0.025, 0.025])
    assert profile.cpu_source == "periodic_subprocess_sampler"
    assert profile.sampler_polls >= 2


def test_resource_watcher_periodic_sampling_can_be_disabled():
    """A caller that knows the substrate is purely in-process can opt out;
    the profile then reports the start/stop-delta source."""
    watcher = ResourceWatcher.for_self(periodic_sampling=False)
    watcher.start()
    time.sleep(0.02)
    watcher.stop()
    profile = watcher.build_profile([0.01, 0.01])
    assert profile.cpu_source == "start_stop_delta"
    assert profile.sampler_polls == 0


def test_resource_watcher_periodic_sampling_captures_subprocess_cpu():
    """Spawn a short-lived child subprocess that consumes measurable CPU; the
    periodic sampler should see it even if start()/stop() bracket-samples
    miss it. (The bracket samples DO see this child because it's a long-
    lived enough subprocess; the test pin is more about ensuring the
    sampler runs and contributes a non-zero CPU number.)"""
    import subprocess
    import sys

    watcher = ResourceWatcher.for_self(periodic_sampling=True, poll_interval_s=0.02)
    watcher.start()
    # spawn a child that burns ~50ms of CPU
    child = subprocess.Popen([
        sys.executable, "-c",
        "x = 0\nfor i in range(2_000_000): x += i\n"
    ])
    child.wait(timeout=5)
    watcher.stop()
    profile = watcher.build_profile([0.05, 0.05])
    assert profile.cpu_source == "periodic_subprocess_sampler"
    # the sampler observed at least one descendant during the run
    assert profile.process_count_max >= 1
    # cpu_total should be greater than zero — either from the parent or the child
    cpu_total = profile.batch_cpu_time_user_s + profile.batch_cpu_time_system_s
    assert cpu_total > 0


def test_periodic_sampler_rejects_zero_interval():
    from ophamin.instrumenting.periodic_sampler import PeriodicSubprocessSampler
    with pytest.raises(ValueError, match="poll_interval_s must be > 0"):
        PeriodicSubprocessSampler.for_self(poll_interval_s=0)


def test_periodic_sampler_state_to_dict_is_serializable():
    from ophamin.instrumenting.periodic_sampler import PeriodicSubprocessSampler
    sampler = PeriodicSubprocessSampler.for_self(poll_interval_s=0.02)
    sampler.start()
    time.sleep(0.06)
    sampler.stop()
    d = sampler.state.to_dict()
    assert "cpu_time_total_s" in d
    assert d["cpu_time_total_s"] == pytest.approx(
        d["cpu_time_user_s"] + d["cpu_time_system_s"]
    )
    assert d["n_polls"] >= 1
    assert isinstance(d["errors"], list)


def test_periodic_sampler_double_start_raises():
    from ophamin.instrumenting.periodic_sampler import PeriodicSubprocessSampler
    sampler = PeriodicSubprocessSampler.for_self(poll_interval_s=0.02)
    sampler.start()
    try:
        with pytest.raises(RuntimeError, match="already started"):
            sampler.start()
    finally:
        sampler.stop()


def test_periodic_sampler_stop_without_start_is_noop():
    from ophamin.instrumenting.periodic_sampler import PeriodicSubprocessSampler
    sampler = PeriodicSubprocessSampler.for_self()
    sampler.stop()  # must not raise
    assert sampler.state.n_polls == 0
