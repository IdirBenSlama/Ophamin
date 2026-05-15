"""seeing/telemetry/ — consume Kimera's existing observability streams.

Kimera-SWM already exports metrics: ``kimera_swm/infrastructure/monitoring/``
contains a Prometheus exporter, Grafana dashboards, Alertmanager rules, a
distributed tracer, and a structured logger. From CLAUDE.md + the live
KimeraInventory probe (2026-05-15): **35 telemetry surfaces, all live**.

Per the v0.2 reframing (docs/KIMERA_OBSERVATIONAL_SURFACE_2026_05_15.md §4.3),
the highest-leverage move is to **consume** that telemetry rather than
re-implement it. This subpackage is the consumer side.

Phase 0:

    PrometheusScrapeProbe   passive HTTP scrape of /metrics → PrometheusSnapshot
    PrometheusSnapshot      one frozen, content-addressed scrape result
                            (metric families × samples × scraped_at)
    align_to_window         pair a scrape series with a scenario's run window
                            (timestamps before / during / after) for
                            cross-stratum correlation (the Σ pillar).
"""

from ophamin.seeing.telemetry.prometheus_probe import (
    PROMETHEUS_AVAILABLE,
    DEFAULT_PROMETHEUS_URL,
    DEFAULT_SCRAPE_TIMEOUT_S,
    DEFAULT_SIGN_KEY,
    AlignedTelemetryWindow,
    MetricFamilySnapshot,
    MetricSample,
    PrometheusScrapeProbe,
    PrometheusSnapshot,
    TelemetryDependencyMissing,
    TelemetryScrapeError,
    align_to_window,
)

__all__ = [
    "AlignedTelemetryWindow",
    "DEFAULT_PROMETHEUS_URL",
    "DEFAULT_SCRAPE_TIMEOUT_S",
    "DEFAULT_SIGN_KEY",
    "MetricFamilySnapshot",
    "MetricSample",
    "PROMETHEUS_AVAILABLE",
    "PrometheusScrapeProbe",
    "PrometheusSnapshot",
    "TelemetryDependencyMissing",
    "TelemetryScrapeError",
    "align_to_window",
]
