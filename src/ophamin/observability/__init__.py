"""OpenTelemetry observability for Ophamin scenario execution.

Light-touch instrumentation — every read + run operation exposed
through the shared interfaces (:mod:`ophamin.interfaces._impls`)
emits OTel spans + metrics when an OTel provider is configured.
When no provider is configured (the default), the OpenTelemetry API
returns no-op tracers and meters, so the instrumentation costs near
nothing on the hot path.

Public functions:

- :func:`setup_otel` — opt-in helper that wires an OTLP HTTP
  exporter + a basic resource (``service.name = "ophamin"``).
  Use it from your application entry point, before constructing
  any Ophamin scenario.
- :func:`get_tracer` / :func:`get_meter` — accessors for the
  Ophamin-namespaced tracer + meter. Useful when instrumenting
  your own substrate adapter alongside Ophamin's built-in spans.

Conventions:

- Span names follow ``ophamin.<surface>.<operation>``:
  ``ophamin.scenario.run``, ``ophamin.proof.verify``,
  ``ophamin.canonical.encode``.
- Span attributes follow the
  `OpenTelemetry semantic conventions <https://opentelemetry.io/docs/specs/semconv/>`_
  for stable names where applicable; framework-specific attributes
  use the ``ophamin.*`` namespace.
- Metric names follow
  ``ophamin_<surface>_<operation>_<unit-or-action>``:
  ``ophamin_scenarios_run_total``,
  ``ophamin_scenario_duration_seconds``,
  ``ophamin_proofs_verified_total``.

The instrumentation is **always-on at the API surface**: tracer +
meter calls happen regardless of whether a backend is configured.
The OTel API's no-op providers ensure this costs ~10-100 ns per
call, which is far below scenario-run latency.
"""

from __future__ import annotations

from ophamin.observability.otel import (
    DEFAULT_SERVICE_NAME,
    INSTRUMENTATION_NAME,
    INSTRUMENTATION_VERSION,
    OphaminInstrumentor,
    get_meter,
    get_tracer,
    setup_otel,
)

__all__ = [
    "DEFAULT_SERVICE_NAME",
    "INSTRUMENTATION_NAME",
    "INSTRUMENTATION_VERSION",
    "OphaminInstrumentor",
    "get_meter",
    "get_tracer",
    "setup_otel",
]
