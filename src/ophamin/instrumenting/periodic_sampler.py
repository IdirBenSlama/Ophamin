"""Periodic subprocess sampler — bridges the short-lived-subprocess
attribution gap.

A naïve ``ResourceWatcher`` brackets a batch with one snapshot before and
one after. For substrates that run *in-process* (MockSubstrate, simple
adapters), this is correct: the parent process accumulates the CPU and the
deltas are accurate. For substrates that spawn a **short-lived subprocess**
(the production ``KimeraAdapter`` runs the batch in a fresh Python
subprocess), the start/stop snapshots miss the subprocess entirely — it
hasn't started yet at start, and it's already dead at stop. The result: CPU
attribution near zero, masking the substrate's real cost.

The fix is a background thread that polls the process tree at a short
interval (default 100ms) during the batch. Each poll records the *high-
water-mark* CPU time per descendant PID; at the end, summing across all PIDs
ever seen gives the correct subprocess-inclusive total. RSS peak is updated
the same way.

Loud-failure: errors in the polling loop are surfaced via the watcher
metadata, never silently swallowed.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import psutil

DEFAULT_POLL_INTERVAL_S = 0.1


@dataclass
class _PIDHighWater:
    """Highest CPU + RSS ever seen for one descendant PID."""

    cpu_user_s: float = 0.0
    cpu_system_s: float = 0.0
    rss_peak: int = 0
    threads_max: int = 0
    page_faults: int = 0


@dataclass
class PeriodicSamplerState:
    """Public read-only view of what the periodic sampler observed.

    The dataclass is mutable but the watcher keeps a single instance per
    sampler; downstream code should treat the values as a snapshot at the
    time of inspection, not a live stream.
    """

    cpu_time_user_s: float = 0.0
    cpu_time_system_s: float = 0.0
    rss_peak: int = 0
    threads_max: int = 0
    processes_observed: int = 0
    page_faults_total: int = 0
    n_polls: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cpu_time_user_s": self.cpu_time_user_s,
            "cpu_time_system_s": self.cpu_time_system_s,
            "cpu_time_total_s": self.cpu_time_user_s + self.cpu_time_system_s,
            "rss_peak": self.rss_peak,
            "threads_max": self.threads_max,
            "processes_observed": self.processes_observed,
            "page_faults_total": self.page_faults_total,
            "n_polls": self.n_polls,
            "errors": list(self.errors),
        }


class PeriodicSubprocessSampler:
    """Polls a process tree on a background thread until told to stop.

    Construction:

      PeriodicSubprocessSampler.for_self()       polls the current process tree
      PeriodicSubprocessSampler.for_pid(pid)     polls a specific PID's tree

    Usage:

      sampler = PeriodicSubprocessSampler.for_self()
      sampler.start()
      ... batch runs ...
      sampler.stop()
      state = sampler.state

    Designed to be cheap: ~100 µs per poll on a typical Python process tree.
    Default 100ms interval contributes <0.1% wall-time overhead.
    """

    def __init__(
        self,
        pid: int | None = None,
        *,
        poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
    ) -> None:
        if poll_interval_s <= 0:
            raise ValueError(f"poll_interval_s must be > 0, got {poll_interval_s}")
        self._pid = pid
        self._interval = float(poll_interval_s)
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._pid_history: dict[int, _PIDHighWater] = {}
        self.state = PeriodicSamplerState()
        self._lock = threading.Lock()

    @classmethod
    def for_self(cls, **kwargs: object) -> "PeriodicSubprocessSampler":
        return cls(pid=None, **kwargs)  # type: ignore[arg-type]

    @classmethod
    def for_pid(cls, pid: int, **kwargs: object) -> "PeriodicSubprocessSampler":
        return cls(pid=pid, **kwargs)  # type: ignore[arg-type]

    # -- thread lifecycle ---------------------------------------------

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("PeriodicSubprocessSampler already started")
        self._stop_event.clear()
        # capture an initial sample so partial-batch reads still produce
        # something useful
        self._poll_once()
        self._thread = threading.Thread(
            target=self._loop, name="ophamin-periodic-sampler", daemon=True
        )
        self._thread.start()

    def stop(self, timeout_s: float = 1.0) -> None:
        if self._thread is None:
            return
        self._stop_event.set()
        self._thread.join(timeout=timeout_s)
        # one final sample to catch a long-lived subprocess that wrote CPU
        # right before exiting
        self._poll_once()
        self._thread = None

    # -- the polling loop ---------------------------------------------

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._poll_once()
            except Exception as exc:  # noqa: BLE001 — surface to state.errors
                with self._lock:
                    self.state.errors.append(
                        f"{type(exc).__name__}: {exc}"[:240]
                    )
            self._stop_event.wait(self._interval)

    def _poll_once(self) -> None:
        try:
            root = psutil.Process(self._pid if self._pid is not None else os.getpid())
        except psutil.NoSuchProcess:
            return
        try:
            descendants = root.children(recursive=True)
        except psutil.NoSuchProcess:
            descendants = []
        all_procs = [root] + descendants

        threads = 0
        proc_count = 0
        for p in all_procs:
            try:
                t = p.cpu_times()
                m = p.memory_info()
                pid = p.pid
                with self._lock:
                    hw = self._pid_history.setdefault(pid, _PIDHighWater())
                    # high-water-mark per descendant
                    u = float(getattr(t, "user", 0.0))
                    s = float(getattr(t, "system", 0.0))
                    if u > hw.cpu_user_s:
                        hw.cpu_user_s = u
                    if s > hw.cpu_system_s:
                        hw.cpu_system_s = s
                    rss = int(getattr(m, "rss", 0))
                    if rss > hw.rss_peak:
                        hw.rss_peak = rss
                    try:
                        nt = int(p.num_threads())
                        if nt > hw.threads_max:
                            hw.threads_max = nt
                        threads = max(threads, nt)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                    try:
                        full = p.memory_full_info()
                        pf = int(getattr(full, "pfaults", 0))
                        if pf > hw.page_faults:
                            hw.page_faults = pf
                    except (psutil.AccessDenied, AttributeError, psutil.NoSuchProcess):
                        pass
                proc_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        with self._lock:
            self.state.n_polls += 1
            self.state.processes_observed = max(self.state.processes_observed, proc_count)
            self.state.threads_max = max(self.state.threads_max, threads)
            # recompute aggregate from the high-water history
            self.state.cpu_time_user_s = sum(hw.cpu_user_s for hw in self._pid_history.values())
            self.state.cpu_time_system_s = sum(hw.cpu_system_s for hw in self._pid_history.values())
            self.state.rss_peak = max(
                (hw.rss_peak for hw in self._pid_history.values()), default=0
            )
            self.state.page_faults_total = sum(
                hw.page_faults for hw in self._pid_history.values()
            )
