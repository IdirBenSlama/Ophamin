"""OpenTelemetry tracer + meter accessors + opt-in setup helper.

When no OTel SDK provider is configured (the default case after
just ``import ophamin``), :func:`get_tracer` returns a no-op tracer
and :func:`get_meter` returns a no-op meter. The instrumentation
points in :mod:`ophamin.interfaces._impls` use these accessors
unconditionally, so the cost when nothing is exporting is the
overhead of a no-op span (~100 ns per call, dominated by attribute
construction).

Call :func:`setup_otel` from your application entry point if you
want to ship telemetry to a backend. Or wire your own OTel SDK
provider before importing Ophamin scenarios — the API accessors
will pick it up automatically (this is the standard OTel
provider-discovery pattern).
"""

from __future__ import annotations

import os
from typing import Any

from opentelemetry import metrics, trace

from ophamin import __version__

#: Identifier used as ``service.name`` when :func:`setup_otel` is
#: called without an override. Backends typically group spans by
#: service.name, so consistent naming across deployments matters.
DEFAULT_SERVICE_NAME: str = "ophamin"

#: Name attached to the Ophamin-namespaced tracer + meter so
#: backends can distinguish Ophamin spans from caller spans. Per
#: OpenTelemetry semantic conventions for instrumentation libraries.
INSTRUMENTATION_NAME: str = "ophamin"

#: Version attached to the instrumentation. Tracks the framework's
#: own version so a span emitted under Ophamin 0.20.0 is
#: distinguishable from one emitted under 0.21.0.
INSTRUMENTATION_VERSION: str = __version__


def get_tracer() -> trace.Tracer:
    """Return the Ophamin-namespaced :class:`opentelemetry.trace.Tracer`.

    When no SDK provider is configured, this returns a no-op tracer
    whose ``start_as_current_span`` is a near-free context manager.
    Call sites need not check whether OTel is configured.
    """
    return trace.get_tracer(INSTRUMENTATION_NAME, INSTRUMENTATION_VERSION)


def get_meter() -> metrics.Meter:
    """Return the Ophamin-namespaced :class:`opentelemetry.metrics.Meter`.

    When no SDK provider is configured, this returns a no-op meter
    whose instrument creators return no-op counters / histograms.
    """
    return metrics.get_meter(INSTRUMENTATION_NAME, INSTRUMENTATION_VERSION)


def setup_otel(
    *,
    service_name: str = DEFAULT_SERVICE_NAME,
    otlp_endpoint: str | None = None,
    enable_console_exporter: bool = False,
) -> None:
    """Opt-in setup: wire an OTLP HTTP exporter (and optional
    console exporter) onto Ophamin's tracer + meter.

    Idempotent: re-calls after the first one are no-ops (the
    OpenTelemetry SDK enforces single-provider semantics).

    Args:
        service_name: ``service.name`` resource attribute. Defaults
            to ``"ophamin"``; override for multi-deployment
            distinguishability (``"ophamin-prod"``,
            ``"ophamin-ci"``).
        otlp_endpoint: the OTLP HTTP collector endpoint
            (e.g. ``"http://otel-collector:4318"``). If ``None`` AND
            the ``OTEL_EXPORTER_OTLP_ENDPOINT`` env var is set, that
            value is used. If both are unset, no OTLP exporter is
            wired (useful when only the console exporter is wanted,
            or when calling code wires its own exporter later).
        enable_console_exporter: if True, also attach a console
            span exporter that prints spans to stderr (useful for
            local debugging). Default: False.

    Raises:
        RuntimeError: if the ``[telemetry]`` extra (``opentelemetry-sdk``
            + the OTLP exporter packages) is not installed.
    """
    try:
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import (
            ConsoleMetricExporter,
            PeriodicExportingMetricReader,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
        )
    except ImportError as exc:
        raise RuntimeError(
            "setup_otel requires the [telemetry] extra; install via "
            "`pip install 'ophamin[telemetry]'`. The underlying "
            f"import failed: {exc}"
        ) from exc

    resource = Resource.create({
        "service.name": service_name,
        "service.version": __version__,
    })

    # Tracer provider — set up once, idempotent on re-call.
    if not isinstance(trace.get_tracer_provider(), TracerProvider):
        tp = TracerProvider(resource=resource)
        trace.set_tracer_provider(tp)
    else:
        existing = trace.get_tracer_provider()
        assert isinstance(existing, TracerProvider)
        tp = existing

    # Resolve OTLP endpoint from arg or env.
    endpoint = otlp_endpoint or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )
        except ImportError as exc:
            raise RuntimeError(
                "OTLP HTTP span exporter not installed; ensure "
                "opentelemetry-exporter-otlp-proto-http is in your env "
                "(it's part of the [telemetry] extra). "
                f"Underlying ImportError: {exc}"
            ) from exc
        tp.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces"))
        )

    if enable_console_exporter:
        tp.add_span_processor(
            BatchSpanProcessor(ConsoleSpanExporter())
        )

    # Meter provider — same idempotent pattern.
    readers: list[Any] = []
    if endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
                OTLPMetricExporter,
            )
        except ImportError:
            # Metrics-export is optional; trace-only export is a
            # valid deployment.
            pass
        else:
            readers.append(
                PeriodicExportingMetricReader(
                    OTLPMetricExporter(endpoint=f"{endpoint}/v1/metrics")
                )
            )
    if enable_console_exporter:
        readers.append(
            PeriodicExportingMetricReader(ConsoleMetricExporter())
        )

    if not isinstance(metrics.get_meter_provider(), MeterProvider) and readers:
        mp = MeterProvider(resource=resource, metric_readers=readers)
        metrics.set_meter_provider(mp)


class OphaminInstrumentor:
    """Lazy facade for Ophamin's tracer + meter + the framework's
    standard set of metric instruments.

    Instrument construction is deferred until first use so importing
    :mod:`ophamin.observability` doesn't force the OTel SDK to be
    present. The instruments are created on a no-op meter when no
    SDK provider is configured.

    Standard metrics:

    - ``ophamin_scenarios_run_total`` (Counter) —
      attrs: ``scenario``, ``family``, ``tier``, ``outcome``.
    - ``ophamin_scenario_duration_seconds`` (Histogram) —
      attrs: ``scenario``, ``family``.
    - ``ophamin_proofs_verified_total`` (Counter) —
      attrs: ``verified``, ``outcome``.
    - ``ophamin_canonical_bytes_encoded`` (Histogram, unit=bytes) —
      attrs: (none — global distribution).
    """

    _instance: "OphaminInstrumentor | None" = None

    @classmethod
    def get(cls) -> "OphaminInstrumentor":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self._tracer = get_tracer()
        meter = get_meter()
        self.scenarios_run = meter.create_counter(
            name="ophamin_scenarios_run_total",
            description=(
                "Number of scenario runs completed, broken down by "
                "outcome. Increment happens after the scenario emits "
                "its signed proof."
            ),
            unit="1",
        )
        self.scenario_duration = meter.create_histogram(
            name="ophamin_scenario_duration_seconds",
            description=(
                "Wall-clock duration of scenario runs, from the start "
                "of run() to the signed-proof return."
            ),
            unit="s",
        )
        self.proofs_verified = meter.create_counter(
            name="ophamin_proofs_verified_total",
            description=(
                "Number of proof-verification operations, broken down "
                "by whether the HMAC matched + the verdict outcome of "
                "the proof body."
            ),
            unit="1",
        )
        self.canonical_bytes = meter.create_histogram(
            name="ophamin_canonical_bytes_encoded",
            description=(
                "Size in bytes of canonical encodings produced. Useful "
                "for sizing message bus quotas + transport budgets."
            ),
            unit="By",
        )

    @property
    def tracer(self) -> trace.Tracer:
        return self._tracer

    @classmethod
    def reset(cls) -> None:
        """Clear the cached instance (for tests only)."""
        cls._instance = None
