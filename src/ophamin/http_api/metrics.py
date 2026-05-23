"""Prometheus metrics for the Ophamin HTTP API.

The 0.57.0 ``/metrics`` endpoint emitted only two stateless gauges
(``ophamin_build_info`` + ``ophamin_scenarios_registered``). 0.61.0
expands this into ~30 signals across six categories:

* **Framework identity & health** — uptime, python runtime,
  synthetic health gauge.
* **Scenarios** — registered counts (per tier / family) AND
  run counters + duration histogram + failure counters
  (hooked in :class:`Scenario.run_and_persist`).
* **Proof bundles** — bundle counts (per tier / scenario /
  verdict), storage bytes, latest-bundle timestamp per
  scenario, render-failure counters.
* **HTTP API** — request counter + duration histogram +
  in-flight gauge (wired via FastAPI middleware).
* **Process resources** — CPU / RSS / FDs / threads / page
  faults via ``psutil``.
* **Substrate cycles** — counter + duration histogram +
  failure counter + last Φ gauge + halt-mode distribution
  (hooked in :class:`Scenario.run`).

The module exposes a single global :class:`OphaminMetrics`
instance (``METRICS``) that's safe to import anywhere — it owns
the ``CollectorRegistry`` plus all stateful collectors. Stateless
gauges (uptime, bundles, resources) are computed at scrape time
inside :func:`render_exposition`.

The split between stateful + scrape-time matters: stateful
counters (HTTP requests, scenario runs) MUST persist across
scrapes; stateless gauges (bundle counts) should not stale (they
reflect ground truth on disk every scrape). Mixing the two requires
care — see :func:`render_exposition` for the unified path.
"""

from __future__ import annotations

import os
import platform
import time
from pathlib import Path
from typing import Any, Callable

import psutil
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
)

from ophamin import __version__
from ophamin.http_api.bundle_browser import bundle_tree


#: Process start time used by ``ophamin_uptime_seconds``. Captured at
#: module import — that's the first moment the metrics layer is alive,
#: which is what "uptime" should mean for an /metrics scrape.
_PROCESS_START_TIME: float = time.time()


#: Default histogram buckets for scenario + substrate cycle duration
#: (seconds). Covers the operational range from sub-millisecond
#: micro-bench to 10-minute long-form runs.
_DURATION_BUCKETS: tuple[float, ...] = (
    0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5, 10, 30, 60, 300, 600,
)

#: Default histogram buckets for HTTP request latency (seconds).
#: Tighter than scenario buckets — HTTP requests should mostly be <1s.
_HTTP_LATENCY_BUCKETS: tuple[float, ...] = (
    0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10,
)


class OphaminMetrics:
    """Owns the module-level Prometheus registry + all stateful collectors.

    Stateful collectors (Counter, Histogram, Gauge with in-process
    state) live here so values persist across ``/metrics`` scrapes.
    Stateless gauges (built per-scrape from on-disk + psutil) live
    in :func:`render_exposition`.

    Instantiated once at module import as :data:`METRICS`. Tests can
    pass ``reset=True`` to a fresh instance if they need an isolated
    registry (rare — most tests use the global one).
    """

    def __init__(self) -> None:
        self.registry = CollectorRegistry()

        # ------ scenarios ------
        self.scenario_runs_total = Counter(
            "ophamin_scenario_runs_total",
            "Total scenario runs completed, labeled by scenario name + verdict.",
            ["scenario", "verdict"],
            registry=self.registry,
        )
        self.scenario_run_duration_seconds = Histogram(
            "ophamin_scenario_run_duration_seconds",
            "End-to-end scenario run duration (seconds), from run() entry to "
            "signed-record return.",
            ["scenario"],
            buckets=_DURATION_BUCKETS,
            registry=self.registry,
        )
        self.scenario_run_failures_total = Counter(
            "ophamin_scenario_run_failures_total",
            "Scenario runs that raised an exception, labeled by exception type.",
            ["scenario", "exception"],
            registry=self.registry,
        )

        # ------ proof bundles — render failures ------
        self.proof_render_failures_total = Counter(
            "ophamin_proof_render_failures_total",
            "Proof-bundle render failures per format. format ∈ "
            "{json,markdown,html,latex,pdf}.",
            ["format"],
            registry=self.registry,
        )

        # ------ HTTP API ------
        self.http_requests_total = Counter(
            "ophamin_http_requests_total",
            "Total HTTP requests, labeled by method + path + status code.",
            ["method", "path", "status"],
            registry=self.registry,
        )
        self.http_request_duration_seconds = Histogram(
            "ophamin_http_request_duration_seconds",
            "HTTP request handling duration (seconds), labeled by method + path.",
            ["method", "path"],
            buckets=_HTTP_LATENCY_BUCKETS,
            registry=self.registry,
        )
        self.http_requests_in_flight = Gauge(
            "ophamin_http_requests_in_flight",
            "Currently active HTTP requests being processed.",
            registry=self.registry,
        )

        # ------ substrate cycles ------
        self.substrate_cycles_total = Counter(
            "ophamin_substrate_cycles_total",
            "Total substrate cycles observed across all runs.",
            ["substrate"],
            registry=self.registry,
        )
        self.substrate_cycle_duration_seconds = Histogram(
            "ophamin_substrate_cycle_duration_seconds",
            "Substrate-cycle wall-time (seconds), computed as "
            "scenario.batch_duration / n_cycles.",
            ["substrate"],
            buckets=_DURATION_BUCKETS,
            registry=self.registry,
        )
        self.substrate_cycle_failures_total = Counter(
            "ophamin_substrate_cycle_failures_total",
            "Substrate cycles that returned success=False, labeled by error kind.",
            ["substrate", "kind"],
            registry=self.registry,
        )
        self.substrate_last_phi = Gauge(
            "ophamin_substrate_last_phi",
            "Most-recent Φ value observed from substrate cycles, "
            "labeled by substrate name. NaN if no cycle has emitted phi yet.",
            ["substrate"],
            registry=self.registry,
        )
        self.substrate_halt_reason_total = Counter(
            "ophamin_substrate_halt_reason_total",
            "Substrate-cycle halt-mode distribution. halt ∈ "
            "{M1_commit, M2_amplitude_death, M3_rollback, M4_lateral_leap, "
            "selective, exhausted, exception, ...}",
            ["substrate", "halt"],
            registry=self.registry,
        )

    # ----------------------------------------------------------------
    # Convenience hooks — exposed so scenario / persist / substrate
    # call-sites can record without importing module internals.
    # ----------------------------------------------------------------

    def record_scenario_run(
        self,
        *,
        scenario_name: str,
        verdict: str,
        duration_seconds: float,
    ) -> None:
        """Record a completed scenario run."""
        self.scenario_runs_total.labels(scenario=scenario_name, verdict=verdict).inc()
        self.scenario_run_duration_seconds.labels(scenario=scenario_name).observe(
            duration_seconds,
        )

    def record_scenario_failure(
        self, *, scenario_name: str, exception: str,
    ) -> None:
        """Record a scenario run that raised."""
        self.scenario_run_failures_total.labels(
            scenario=scenario_name, exception=exception,
        ).inc()

    def record_render_failure(self, *, format_name: str) -> None:
        self.proof_render_failures_total.labels(format=format_name).inc()

    def record_substrate_batch(
        self,
        *,
        substrate_name: str,
        cycle_results: list[Any],
        batch_duration_seconds: float,
    ) -> None:
        """Record one substrate ``run_batch`` worth of cycles.

        Pulls from ``CycleResult.success``, ``CycleResult.error``,
        ``CycleResult.halt_mode``, and ``CycleResult.raw["phi"]`` (when
        present). Wall-time per cycle is the batch duration divided by
        cycle count (best available without a per-cycle wrapper).
        """
        n = len(cycle_results)
        if n == 0:
            return
        per_cycle_duration = batch_duration_seconds / n
        last_phi: float | None = None
        for cr in cycle_results:
            self.substrate_cycles_total.labels(substrate=substrate_name).inc()
            self.substrate_cycle_duration_seconds.labels(
                substrate=substrate_name,
            ).observe(per_cycle_duration)
            if not getattr(cr, "success", True):
                kind = getattr(cr, "error", None) or "unknown"
                # Truncate huge tracebacks to a short kind label.
                kind = str(kind).split("\n")[0][:60]
                self.substrate_cycle_failures_total.labels(
                    substrate=substrate_name, kind=kind,
                ).inc()
            halt = getattr(cr, "halt_mode", None)
            if halt:
                self.substrate_halt_reason_total.labels(
                    substrate=substrate_name, halt=halt,
                ).inc()
            raw = getattr(cr, "raw", None) or {}
            phi = raw.get("phi")
            if isinstance(phi, (int, float)):
                last_phi = float(phi)
        if last_phi is not None:
            self.substrate_last_phi.labels(substrate=substrate_name).set(last_phi)


#: Module-level singleton. Tests + production both import this.
METRICS = OphaminMetrics()


# --------------------------------------------------------------------------
# Scrape-time exposition — builds a unified text response combining the
# stateful (METRICS.registry) + stateless (this scrape) gauges.
# --------------------------------------------------------------------------


def _proofs_root() -> Path:
    """The proofs/ root the exposition walks. Operator can override
    via OPHAMIN_PROOFS_ROOT env var; default is `proofs/` relative
    to the process cwd (matches how Scenario.run_and_persist writes)."""
    return Path(os.environ.get("OPHAMIN_PROOFS_ROOT", "proofs"))


def _disk_free_bytes(path: Path) -> int:
    """Free bytes on the filesystem hosting ``path``. Returns -1 on error.

    Used by the disk_free gauge — operators watch this to know when
    proof bundles are about to fill the disk.
    """
    try:
        stat = os.statvfs(path if path.exists() else path.parent if path.parent.exists() else "/")
        return stat.f_bavail * stat.f_frsize
    except OSError:
        return -1


def _walk_bundle_storage(root: Path) -> int:
    """Sum file sizes under ``root``. 0 if root doesn't exist."""
    if not root.is_dir():
        return 0
    total = 0
    try:
        for p in root.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    continue
    except OSError:
        pass
    return total


def _build_scrape_time_registry() -> CollectorRegistry:
    """Build a fresh registry of the stateless gauges for this scrape.

    Stateless gauges reflect ground truth on disk + live process state —
    we recompute every scrape rather than caching, so an operator who
    adds bundles + scrapes /metrics sees the new totals immediately.
    """
    from ophamin.measuring.scenarios import SCENARIOS

    r = CollectorRegistry()

    # ---- framework identity / health ----
    Info(
        "ophamin_build",
        "Ophamin framework build identity",
        registry=r,
    ).info({"version": __version__, "name": "ophamin-http-api"})

    Info(
        "ophamin_python_runtime",
        "Python interpreter + platform identity.",
        registry=r,
    ).info({
        "python_version": platform.python_version(),
        "platform": platform.platform(terse=True),
        "implementation": platform.python_implementation(),
    })

    Gauge(
        "ophamin_uptime_seconds",
        "Seconds since the metrics module was imported.",
        registry=r,
    ).set(time.time() - _PROCESS_START_TIME)

    # health = AND over: proofs_root accessible, registry non-empty, process up
    proofs_root = _proofs_root()
    health = 1.0
    if not proofs_root.is_dir():
        health = 0.0
    if not SCENARIOS:
        health = 0.0
    Gauge(
        "ophamin_health",
        "Synthetic health: 1 = all sub-checks pass, 0 = degraded.",
        registry=r,
    ).set(health)

    # ---- scenarios — counts by tier + family ----
    Gauge(
        "ophamin_scenarios_registered",
        "Total scenarios in the registry.",
        registry=r,
    ).set(len(SCENARIOS))

    per_tier = Gauge(
        "ophamin_scenarios_registered_by_tier",
        "Scenarios registered per tier.",
        ["tier"],
        registry=r,
    )
    per_family = Gauge(
        "ophamin_scenarios_registered_by_family",
        "Scenarios registered per family.",
        ["family"],
        registry=r,
    )
    tier_counts: dict[str, int] = {}
    family_counts: dict[str, int] = {}
    for cls in SCENARIOS.values():
        t = cls.tier.value if hasattr(cls.tier, "value") else str(cls.tier)
        tier_counts[t] = tier_counts.get(t, 0) + 1
        f = getattr(cls, "family", "") or "unknown"
        family_counts[f] = family_counts.get(f, 0) + 1
    for t, c in tier_counts.items():
        per_tier.labels(tier=t).set(c)
    for f, c in family_counts.items():
        per_family.labels(family=f).set(c)

    # ---- proof bundles ----
    tree = bundle_tree(proofs_root)
    Gauge(
        "ophamin_proof_bundles_total",
        "Total signed proof bundles on disk under the configured proofs/ root.",
        registry=r,
    ).set(tree["totals"]["bundles"])

    by_tier = Gauge(
        "ophamin_proof_bundles_by_tier",
        "Proof bundles per tier.",
        ["tier"],
        registry=r,
    )
    by_scenario = Gauge(
        "ophamin_proof_bundles_by_scenario",
        "Proof bundles per scenario.",
        ["tier", "scenario"],
        registry=r,
    )
    verdict_counter = Gauge(
        "ophamin_proof_verdicts",
        "Proof bundles by verdict outcome.",
        ["verdict"],
        registry=r,
    )
    latest_ts = Gauge(
        "ophamin_proof_latest_timestamp",
        "Latest bundle date per scenario (Unix epoch seconds, midnight UTC).",
        ["tier", "scenario"],
        registry=r,
    )
    for tier in tree["tiers"]:
        tier_n = sum(len(s["bundles"]) for s in tier["scenarios"])
        by_tier.labels(tier=tier["tier"]).set(tier_n)
        for sc in tier["scenarios"]:
            by_scenario.labels(tier=tier["tier"], scenario=sc["scenario"]).set(
                len(sc["bundles"]),
            )
            # Bundles are sorted by name (date-first); last is the most recent.
            if sc["bundles"]:
                from datetime import datetime, timezone
                latest_date_str = sc["bundles"][-1]["date"]
                try:
                    dt = datetime.strptime(latest_date_str, "%Y-%m-%d").replace(
                        tzinfo=timezone.utc,
                    )
                    latest_ts.labels(tier=tier["tier"], scenario=sc["scenario"]).set(
                        dt.timestamp(),
                    )
                except ValueError:
                    pass
    for verdict, n in (tree["totals"]["verdicts"] or {}).items():
        verdict_counter.labels(verdict=verdict).set(n)

    Gauge(
        "ophamin_proof_bundle_storage_bytes",
        "Total disk bytes used by the proofs/ tree.",
        registry=r,
    ).set(_walk_bundle_storage(proofs_root))

    Gauge(
        "ophamin_disk_free_bytes",
        "Free bytes on the filesystem hosting the proofs/ root.",
        ["path"],
        registry=r,
    ).labels(path=str(proofs_root)).set(_disk_free_bytes(proofs_root))

    # ---- process resources via psutil ----
    try:
        proc = psutil.Process()
        cpu_times = proc.cpu_times()
        mem = proc.memory_info()
        Gauge(
            "ophamin_process_cpu_seconds_total",
            "Total CPU time consumed by the Ophamin process "
            "(user + system seconds).",
            registry=r,
        ).set(cpu_times.user + cpu_times.system)
        Gauge(
            "ophamin_process_resident_memory_bytes",
            "Resident set size (RSS) of the Ophamin process.",
            registry=r,
        ).set(mem.rss)
        Gauge(
            "ophamin_process_threads",
            "Number of OS threads in the Ophamin process.",
            registry=r,
        ).set(proc.num_threads())
        try:
            Gauge(
                "ophamin_process_open_fds",
                "Open file descriptors in the Ophamin process.",
                registry=r,
            ).set(proc.num_fds())
        except (AttributeError, psutil.AccessDenied):
            # num_fds is POSIX-only; on Windows it's unavailable.
            pass
        try:
            pfaults = proc.memory_full_info().pfaults if hasattr(mem, "pfaults") else None
            if pfaults is None:
                # Fall back to ctx_switches as a coarse proxy.
                pfaults = proc.num_ctx_switches().voluntary
            Gauge(
                "ophamin_process_page_faults_total",
                "Cumulative page faults (best-effort; falls back to voluntary "
                "ctx-switches on platforms without page-fault counters).",
                registry=r,
            ).set(pfaults)
        except (AttributeError, psutil.AccessDenied):
            pass
    except psutil.Error:
        pass

    return r


def render_exposition() -> tuple[bytes, str]:
    """Return ``(body, content_type)`` for the `/metrics` endpoint.

    Concatenates the stateful registry (persisted counters / histograms /
    in-flight gauge) with a fresh stateless registry computed each scrape
    (bundle counts, process stats, etc.). Both contribute their own
    HELP/TYPE lines; the Prometheus text format tolerates two registries
    written back-to-back as long as metric names don't collide — which
    they don't (stateful + stateless use disjoint name sets).
    """
    stateful = generate_latest(METRICS.registry)
    stateless = generate_latest(_build_scrape_time_registry())
    return stateful + stateless, CONTENT_TYPE_LATEST


# --------------------------------------------------------------------------
# FastAPI middleware — wraps every request with timing + counter update.
# --------------------------------------------------------------------------


def http_metrics_middleware_factory() -> Callable[[Any, Any], Any]:
    """Build the FastAPI ASGI middleware that records HTTP metrics.

    Returns a callable suitable for ``app.middleware("http")(fn)``.
    The middleware updates three signals per request:

      * ``ophamin_http_requests_in_flight`` (inc / dec)
      * ``ophamin_http_request_duration_seconds`` (observe)
      * ``ophamin_http_requests_total`` (inc; labeled by method+path+status)

    The ``path`` label is the routed-path *template* (e.g.
    ``/scenarios/{name}/run`` not ``/scenarios/spearman/run``) so the
    label cardinality stays bounded — otherwise every distinct URL
    would create a new time series and Prometheus would balk.
    """
    async def middleware(request: Any, call_next: Any) -> Any:
        # Skip /metrics itself — recursive accounting would just spin.
        # Skip static asset paths so each .css/.js doesn't pollute the
        # label set (FastAPI doesn't template these — they'd land as
        # `/ui/static/styles.css`, `/ui/static/app.js`, etc.).
        path_str = request.url.path
        if (
            path_str == "/metrics"
            or path_str.startswith("/ui/static/")
            or path_str.startswith("/app/static/")
        ):
            return await call_next(request)

        method = request.method
        # The routed path template is on request.scope["route"].path
        # after routing — but routing happens during call_next. To
        # avoid double-routing we read it lazily after the response.
        METRICS.http_requests_in_flight.inc()
        start = time.perf_counter()
        status_code: int = 0
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            status_code = 500
            raise
        finally:
            duration = time.perf_counter() - start
            METRICS.http_requests_in_flight.dec()
            # Read the matched route template if available; fall back to
            # the raw path. This bounds label cardinality.
            route = request.scope.get("route")
            path_template = getattr(route, "path", path_str) if route else path_str
            METRICS.http_request_duration_seconds.labels(
                method=method, path=path_template,
            ).observe(duration)
            METRICS.http_requests_total.labels(
                method=method, path=path_template, status=str(status_code),
            ).inc()

    return middleware
