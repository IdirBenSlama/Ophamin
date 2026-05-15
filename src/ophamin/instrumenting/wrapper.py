"""InstrumentedSubstrate — decorator that captures resource metrics around
any ``SubstrateProbe`` (Kimera adapter, mock, future substrates).

The decorator preserves the substrate's interface and metadata; tests and
scenarios that took a SubstrateUnderTest can take an InstrumentedSubstrate
without changes. The captured BatchResourceProfile is available via
``last_profile()`` after each run_batch.

External-only by design — uses psutil snapshots and the adapter's own
per-cycle wall-time. No Kimera-side changes required.
"""

from __future__ import annotations

import os
from typing import Any

from ophamin.instrumenting.resource_metrics import (
    BatchResourceProfile,
    ResourceWatcher,
)
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest


class InstrumentedSubstrate(SubstrateUnderTest):
    """Wraps any SubstrateProbe and captures resource profiles per batch.

    Drop-in: anywhere the existing four scenarios take a ``KimeraAdapter`` or
    ``MockSubstrate``, ``InstrumentedSubstrate(adapter)`` works in place. The
    last batch's resource profile is read via ``inst.last_profile()`` (None
    if no batch has run yet).

    Per-cycle attribution kind:

      * If the wrapped substrate populates ``cycle_seconds`` in ``raw`` (the
        KimeraAdapter does, in batch mode) the per-cycle wall-times are
        exact; CPU/RSS are batch-averaged proportional to wall-time.
      * If ``cycle_seconds`` is absent, per-cycle wall-time is estimated by
        evenly dividing the batch wall-time across cycles. The profile
        labels this honestly via ``attribution_kind``.
    """

    name = "instrumented"

    def __init__(self, inner: SubstrateUnderTest, *, sample_pid: int | None = None) -> None:
        if not isinstance(inner, SubstrateUnderTest):
            raise TypeError(
                f"InstrumentedSubstrate requires a SubstrateUnderTest; got {type(inner).__name__}"
            )
        self._inner = inner
        # The KimeraAdapter runs the substrate in a subprocess; the parent
        # process is Ophamin's. ``sample_pid`` can be set if the caller
        # knows the subprocess PID — but the adapter doesn't expose that for
        # batch runs, so by default we sample the current process tree
        # (which becomes the subprocess root once it's spawned and joined).
        self._sample_pid = sample_pid
        self._last_profile: BatchResourceProfile | None = None
        # surface the inner substrate's name on the instrumented wrapper for
        # downstream code that displays substrate.name
        self.name = f"instrumented({inner.name})"

    # -- decorator passthroughs ----------------------------------------

    def reset(self) -> None:
        self._inner.reset()

    def run_cycle(self, stimulus: Any, params: dict[str, Any] | None = None) -> CycleResult:
        return self._inner.run_cycle(stimulus, params)

    def run_batch(
        self, stimuli: list[Any], params: dict[str, Any] | None = None
    ) -> list[CycleResult]:
        """Wrap the inner run_batch with a ResourceWatcher; record the profile."""
        watcher = (
            ResourceWatcher.for_pid(self._sample_pid)
            if self._sample_pid is not None
            else ResourceWatcher.for_self()
        )
        watcher.start()
        try:
            results = self._inner.run_batch(stimuli, params)
        finally:
            watcher.stop()

        wall_times = _extract_per_cycle_wall_times(results, watcher)
        self._last_profile = watcher.build_profile(wall_times)
        return results

    def git_commit(self) -> str:
        return self._inner.git_commit()

    def metadata(self) -> dict[str, Any]:
        meta = dict(self._inner.metadata())
        meta["instrumented"] = True
        meta["instrumented_sample_pid"] = self._sample_pid or os.getpid()
        return meta

    # -- profile accessor ----------------------------------------------

    def last_profile(self) -> BatchResourceProfile | None:
        """The BatchResourceProfile from the most recent run_batch, or None."""
        return self._last_profile


def _extract_per_cycle_wall_times(
    results: list[CycleResult], watcher: ResourceWatcher
) -> list[float]:
    """Pull per-cycle wall-time from each CycleResult.raw['cycle_seconds'].

    Falls back to an evenly-divided estimate when ``cycle_seconds`` is absent
    (synthetic / mock substrates that don't populate it). The watcher's
    bracket wall-time is the truth in that fallback.
    """
    walls: list[float] = []
    has_per_cycle = True
    for r in results:
        raw = r.raw or {}
        if isinstance(raw, dict) and isinstance(raw.get("cycle_seconds"), (int, float)):
            walls.append(float(raw["cycle_seconds"]))
        else:
            has_per_cycle = False
            walls.append(0.0)  # placeholder, overwritten below
    if has_per_cycle and walls:
        return walls
    # fall back: divide the bracket wall-time evenly across cycles
    n = max(1, len(results))
    if watcher._start_sample is None or watcher._stop_sample is None:
        return [0.0] * n
    bracket_wall = (
        watcher._stop_sample.captured_at_perf - watcher._start_sample.captured_at_perf
    )
    return [bracket_wall / n] * n
