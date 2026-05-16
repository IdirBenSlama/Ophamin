"""Per-cycle / per-batch resource metrics via psutil — external profiling.

The contract is: snapshot before and after a substrate's ``run_batch``;
attribute the deltas (CPU time, memory peak, page faults, threads) to the
batch as a whole; combine with the adapter's own per-cycle wall-time to
produce a CycleResourceProfile per cycle.

External-only by design — does NOT require any Kimera-side instrumentation.
The cost is approximate per-cycle attribution: CPU/RSS deltas are averaged
across cycles in the batch rather than measured per-cycle. Per-cycle
precision requires the Kimera-side telemetry hook (Tier-2 proposal,
deferred).

A note on subprocess attribution: the Kimera adapter runs the substrate in a
subprocess (one-per-batch in 'batch' mode). The ResourceWatcher samples the
*subprocess group* (Linux: cgroup; macOS: psutil process tree) so the metrics
reflect Kimera's resource use, not Ophamin's. When the substrate is not a
subprocess (e.g. MockSubstrate), it samples the current process.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from statistics import mean, median
from typing import Any

import psutil

from ophamin.instrumenting.periodic_sampler import (
    DEFAULT_POLL_INTERVAL_S,
    PeriodicSubprocessSampler,
)


@dataclass(frozen=True)
class ResourceSample:
    """One psutil snapshot of a process or process-tree."""

    captured_at_perf: float          # time.perf_counter() at capture
    captured_at_wall: float          # time.time() at capture
    cpu_time_user_s: float           # cumulative user-mode CPU seconds
    cpu_time_system_s: float         # cumulative system-mode CPU seconds
    rss_bytes: int                   # resident set size in bytes
    vms_bytes: int                   # virtual memory size in bytes
    num_threads: int
    num_page_faults: int             # minor + major page faults (best-effort)
    process_count: int               # how many processes were sampled
                                     # (root + descendants for subprocess case)

    def to_dict(self) -> dict[str, Any]:
        return {
            "captured_at_perf": self.captured_at_perf,
            "captured_at_wall": self.captured_at_wall,
            "cpu_time_user_s": self.cpu_time_user_s,
            "cpu_time_system_s": self.cpu_time_system_s,
            "rss_bytes": self.rss_bytes,
            "vms_bytes": self.vms_bytes,
            "num_threads": self.num_threads,
            "num_page_faults": self.num_page_faults,
            "process_count": self.process_count,
        }


@dataclass(frozen=True)
class CycleResourceProfile:
    """One cycle's resource attribution.

    Wall-time is per-cycle precise (from the adapter's own cycle_seconds).
    CPU / RSS / page-faults are batch-averaged unless a per-cycle Kimera-
    side hook is wired (Tier-2, deferred).
    """

    cycle_index: int
    wall_time_s: float               # measured per-cycle by the adapter
    cpu_time_attributed_s: float     # batch-avg attribution (user + system / N)
    rss_peak_bytes_attributed: int   # batch peak attributed equally
    page_faults_attributed: int      # batch total / N
    attribution_kind: str            # "per_cycle" | "batch_averaged"

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_index": self.cycle_index,
            "wall_time_s": self.wall_time_s,
            "cpu_time_attributed_s": self.cpu_time_attributed_s,
            "rss_peak_bytes_attributed": self.rss_peak_bytes_attributed,
            "page_faults_attributed": self.page_faults_attributed,
            "attribution_kind": self.attribution_kind,
        }


@dataclass(frozen=True)
class BatchResourceProfile:
    """Per-batch resource summary + per-cycle distributions."""

    n_cycles: int
    batch_wall_time_s: float
    batch_cpu_time_user_s: float
    batch_cpu_time_system_s: float
    batch_page_faults: int
    rss_bytes_before: int
    rss_bytes_after: int
    rss_bytes_peak: int
    num_threads_max: int
    process_count_max: int
    attribution_kind: str               # "per_cycle" | "batch_averaged"
    cpu_source: str                     # "periodic_subprocess_sampler" |
                                        # "start_stop_delta"
    sampler_polls: int = 0              # number of periodic polls during the batch
    per_cycle: tuple[CycleResourceProfile, ...] = ()

    def cycle_wall_distribution(self) -> dict[str, float]:
        return _dist_stats([c.wall_time_s for c in self.per_cycle])

    def cycle_cpu_distribution(self) -> dict[str, float]:
        return _dist_stats([c.cpu_time_attributed_s for c in self.per_cycle])

    def cycle_rss_distribution(self) -> dict[str, float]:
        return _dist_stats([float(c.rss_peak_bytes_attributed) for c in self.per_cycle])

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_cycles": self.n_cycles,
            "batch_wall_time_s": self.batch_wall_time_s,
            "batch_cpu_time_user_s": self.batch_cpu_time_user_s,
            "batch_cpu_time_system_s": self.batch_cpu_time_system_s,
            "batch_cpu_time_total_s": self.batch_cpu_time_user_s + self.batch_cpu_time_system_s,
            "batch_page_faults": self.batch_page_faults,
            "rss_bytes_before": self.rss_bytes_before,
            "rss_bytes_after": self.rss_bytes_after,
            "rss_bytes_peak": self.rss_bytes_peak,
            "num_threads_max": self.num_threads_max,
            "process_count_max": self.process_count_max,
            "attribution_kind": self.attribution_kind,
            "cpu_source": self.cpu_source,
            "sampler_polls": self.sampler_polls,
            "cycle_wall_distribution": self.cycle_wall_distribution(),
            "cycle_cpu_distribution": self.cycle_cpu_distribution(),
            "cycle_rss_distribution": self.cycle_rss_distribution(),
            "per_cycle": [c.to_dict() for c in self.per_cycle],
        }


def _dist_stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {"n": 0, "min": 0.0, "max": 0.0, "median": 0.0, "mean": 0.0, "p10": 0.0, "p90": 0.0}
    sorted_v = sorted(float(v) for v in values)
    n = len(sorted_v)
    return {
        "n": n,
        "min": sorted_v[0],
        "max": sorted_v[-1],
        "median": float(median(sorted_v)),
        "mean": float(mean(sorted_v)),
        "p10": sorted_v[max(0, int(n * 0.10) - 1)],
        "p90": sorted_v[min(n - 1, int(n * 0.90))],
    }


# --------------------------------------------------------------------------
# ResourceWatcher — the load-bearing sampler
# --------------------------------------------------------------------------


class ResourceWatcher:
    """Snapshot a process (+ descendants) before/after a batch.

    Two constructions:

      ResourceWatcher.for_self()         samples the current process tree
      ResourceWatcher.for_pid(pid)       samples a specific PID + descendants

    The watcher captures one snapshot at ``start()`` and another at
    ``stop()``; ``build_profile`` combines them with per-cycle wall-times to
    produce a BatchResourceProfile. Peak-RSS is sampled by ``observe()``
    calls in between (caller's responsibility — psutil RSS-peak across a
    subprocess lifetime is not available natively).
    """

    def __init__(
        self,
        pid: int | None = None,
        *,
        periodic_sampling: bool = True,
        poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
    ) -> None:
        self._pid = pid  # None means "current process"
        self._start_sample: ResourceSample | None = None
        self._stop_sample: ResourceSample | None = None
        self._rss_peak: int = 0
        self._threads_max: int = 0
        self._proc_max: int = 0
        # Periodic-sampler closes the short-lived-subprocess attribution gap
        # (start/stop snapshots miss a subprocess that lives only between
        # them). Enabled by default; callers running purely in-process can
        # disable it via ``periodic_sampling=False`` for marginal overhead
        # savings.
        self._periodic_sampling = periodic_sampling
        self._poll_interval = poll_interval_s
        self._sampler: PeriodicSubprocessSampler | None = None

    @classmethod
    def for_self(cls, **kwargs: object) -> "ResourceWatcher":
        return cls(pid=None, **kwargs)  # type: ignore[arg-type]

    @classmethod
    def for_pid(cls, pid: int, **kwargs: object) -> "ResourceWatcher":
        return cls(pid=pid, **kwargs)  # type: ignore[arg-type]

    # -- one-shot sample ------------------------------------------------

    def sample(self) -> ResourceSample:
        """Take one psutil snapshot of the target process (+ descendants).

        Sums CPU/RSS/VMS across the process and its descendants — robust
        when the substrate spawns subprocesses. Returns a fresh sample;
        does not store it.
        """
        if self._pid is None:
            proc = psutil.Process(os.getpid())
        else:
            try:
                proc = psutil.Process(self._pid)
            except psutil.NoSuchProcess:
                # the subprocess already exited — best-effort empty sample
                return ResourceSample(
                    captured_at_perf=time.perf_counter(),
                    captured_at_wall=time.time(),
                    cpu_time_user_s=0.0,
                    cpu_time_system_s=0.0,
                    rss_bytes=0,
                    vms_bytes=0,
                    num_threads=0,
                    num_page_faults=0,
                    process_count=0,
                )

        # collect this process + its alive descendants
        try:
            descendants = proc.children(recursive=True)
        except psutil.NoSuchProcess:
            descendants = []
        all_procs = [proc] + descendants

        cpu_user = cpu_sys = 0.0
        rss = vms = 0
        threads = 0
        faults = 0
        alive = 0
        for p in all_procs:
            try:
                # cpu_times: user, system (+ children_user, children_system on Linux)
                t = p.cpu_times()
                cpu_user += float(getattr(t, "user", 0.0))
                cpu_sys += float(getattr(t, "system", 0.0))
                m = p.memory_info()
                rss += int(getattr(m, "rss", 0))
                vms += int(getattr(m, "vms", 0))
                threads += int(p.num_threads())
                # page faults via psutil's memory_full_info() when available
                # (not every platform exposes it; tolerate absence)
                try:
                    full = p.memory_full_info()
                    faults += int(getattr(full, "pfaults", 0))
                except (psutil.AccessDenied, AttributeError):
                    pass
                alive += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return ResourceSample(
            captured_at_perf=time.perf_counter(),
            captured_at_wall=time.time(),
            cpu_time_user_s=cpu_user,
            cpu_time_system_s=cpu_sys,
            rss_bytes=rss,
            vms_bytes=vms,
            num_threads=threads,
            num_page_faults=faults,
            process_count=alive,
        )

    # -- bracket a batch -------------------------------------------------

    def start(self) -> None:
        sample = self.sample()
        self._start_sample = sample
        self._rss_peak = sample.rss_bytes
        self._threads_max = sample.num_threads
        self._proc_max = sample.process_count
        # Kick off the background sampler that bridges the short-lived-
        # subprocess attribution gap. The sampler keeps high-water marks
        # per descendant PID, so a subprocess that lives only between
        # start() and stop() still contributes to the totals.
        if self._periodic_sampling:
            self._sampler = (
                PeriodicSubprocessSampler.for_pid(
                    self._pid, poll_interval_s=self._poll_interval
                )
                if self._pid is not None
                else PeriodicSubprocessSampler.for_self(
                    poll_interval_s=self._poll_interval
                )
            )
            self._sampler.start()

    def observe(self) -> ResourceSample:
        """Take an intra-batch sample; updates the running peak RSS / thread
        / process counts."""
        sample = self.sample()
        if sample.rss_bytes > self._rss_peak:
            self._rss_peak = sample.rss_bytes
        if sample.num_threads > self._threads_max:
            self._threads_max = sample.num_threads
        if sample.process_count > self._proc_max:
            self._proc_max = sample.process_count
        return sample

    def stop(self) -> None:
        # stop the periodic sampler FIRST so its final poll catches the
        # subprocess's last CPU usage, then take the bracket stop sample
        if self._sampler is not None:
            self._sampler.stop()
            # merge the sampler's high-water findings into the watcher's
            # accumulators
            ss = self._sampler.state
            if ss.rss_peak > self._rss_peak:
                self._rss_peak = ss.rss_peak
            if ss.threads_max > self._threads_max:
                self._threads_max = ss.threads_max
            if ss.processes_observed > self._proc_max:
                self._proc_max = ss.processes_observed
        sample = self.sample()
        self._stop_sample = sample
        if sample.rss_bytes > self._rss_peak:
            self._rss_peak = sample.rss_bytes

    def build_profile(
        self, per_cycle_wall_times_s: list[float]
    ) -> BatchResourceProfile:
        """Combine the bracket samples + per-cycle wall-times into a profile.

        ``per_cycle_wall_times_s`` is the list of cycle_seconds extracted from
        the substrate's CycleResult.raw (the Kimera adapter emits these
        directly). When unavailable (synthetic substrates), the caller passes
        an evenly-divided estimate; ``attribution_kind`` records which it was.
        """
        if self._start_sample is None or self._stop_sample is None:
            raise RuntimeError(
                "ResourceWatcher.build_profile called without matching start()/stop()"
            )
        start = self._start_sample
        stop = self._stop_sample
        n = max(1, len(per_cycle_wall_times_s))
        batch_wall = stop.captured_at_perf - start.captured_at_perf
        # CPU attribution: prefer the periodic sampler's subprocess-inclusive
        # sums when present; otherwise fall back to the parent's start/stop
        # delta (correct for in-process substrates, undercounts subprocess
        # substrates). Page-faults follow the same precedence.
        if self._sampler is not None and self._sampler.state.n_polls > 0:
            batch_cpu_user = self._sampler.state.cpu_time_user_s
            batch_cpu_sys = self._sampler.state.cpu_time_system_s
            batch_faults = self._sampler.state.page_faults_total
            cpu_source = "periodic_subprocess_sampler"
        else:
            batch_cpu_user = max(0.0, stop.cpu_time_user_s - start.cpu_time_user_s)
            batch_cpu_sys = max(0.0, stop.cpu_time_system_s - start.cpu_time_system_s)
            batch_faults = max(0, stop.num_page_faults - start.num_page_faults)
            cpu_source = "start_stop_delta"
        batch_cpu = batch_cpu_user + batch_cpu_sys

        # per-cycle attribution by wall-time fraction (proportional)
        total_cycle_wall = sum(per_cycle_wall_times_s) or batch_wall
        per_cycle: list[CycleResourceProfile] = []
        for idx, wall in enumerate(per_cycle_wall_times_s):
            share = (wall / total_cycle_wall) if total_cycle_wall > 0 else 1.0 / n
            per_cycle.append(
                CycleResourceProfile(
                    cycle_index=idx,
                    wall_time_s=wall,
                    cpu_time_attributed_s=batch_cpu * share,
                    rss_peak_bytes_attributed=self._rss_peak,  # peak is shared, not divided
                    page_faults_attributed=int(batch_faults * share),
                    attribution_kind="batch_averaged",
                )
            )

        return BatchResourceProfile(
            n_cycles=len(per_cycle),
            batch_wall_time_s=batch_wall,
            batch_cpu_time_user_s=batch_cpu_user,
            batch_cpu_time_system_s=batch_cpu_sys,
            batch_page_faults=batch_faults,
            rss_bytes_before=start.rss_bytes,
            rss_bytes_after=stop.rss_bytes,
            rss_bytes_peak=self._rss_peak,
            num_threads_max=self._threads_max,
            process_count_max=self._proc_max,
            attribution_kind="batch_averaged",
            cpu_source=cpu_source,
            sampler_polls=(
                self._sampler.state.n_polls if self._sampler is not None else 0
            ),
            per_cycle=tuple(per_cycle),
        )
