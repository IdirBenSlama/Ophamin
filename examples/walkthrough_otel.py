"""Concept walkthrough — OpenTelemetry instrumentation (RFC 0002 Phase E9.6).

Demonstrates the **observability interop layer**: every scenario
run, proof verification, and canonical-form encoding emits OTel
spans + metrics that any OTel-receiving backend (Jaeger, Datadog,
Prometheus, Grafana Tempo / Mimir, New Relic, etc.) can ingest
with zero Ophamin-specific configuration on the backend side.

The walkthrough installs OTel's ``InMemorySpanExporter`` +
``InMemoryMetricReader`` to capture spans + metrics that would
otherwise flow to an OTLP collector, then prints them so the
reader can see exactly what shape Ophamin emits.

In production the equivalent setup is::

    from ophamin.observability import setup_otel
    setup_otel(otlp_endpoint="http://otel-collector:4318")

after which every call to ``run_scenario_impl`` /
``verify_proof_impl`` / ``canonicalize_value_impl`` emits its
spans + metrics to the configured collector.

Run with::

    PYTHONPATH=src python examples/walkthrough_otel.py

Safe to import; demo runs only as ``__main__``.
"""

from __future__ import annotations

import json
from pathlib import Path

from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from ophamin import __version__
from ophamin.interfaces._impls import (
    canonicalize_value_impl,
    verify_proof_impl,
)
from ophamin.observability import (
    DEFAULT_SERVICE_NAME,
    INSTRUMENTATION_NAME,
    OphaminInstrumentor,
)
from ophamin.observability import otel as otel_module


REPO_ROOT = Path(__file__).resolve().parent.parent
PROOFS_DIR = REPO_ROOT / "proofs" / "measurement_machinery"


def _install_in_memory_otel() -> dict[str, object]:
    """Install in-memory OTel providers and return the exporters."""
    span_exporter = InMemorySpanExporter()
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(span_exporter))

    metric_reader = InMemoryMetricReader()
    meter_provider = MeterProvider(metric_readers=[metric_reader])

    # Point the framework's accessors at our in-memory providers.
    def _get_tracer() -> trace.Tracer:
        return tracer_provider.get_tracer(INSTRUMENTATION_NAME, __version__)

    def _get_meter() -> metrics.Meter:
        return meter_provider.get_meter(INSTRUMENTATION_NAME, __version__)

    otel_module.get_tracer = _get_tracer  # type: ignore[assignment]
    otel_module.get_meter = _get_meter  # type: ignore[assignment]

    OphaminInstrumentor.reset()

    return {
        "span_exporter": span_exporter,
        "metric_reader": metric_reader,
        "tracer_provider": tracer_provider,
        "meter_provider": meter_provider,
    }


def main() -> None:
    print("# OpenTelemetry walkthrough — RFC 0002 Phase E9.6")
    print()
    print("Ophamin's observability layer emits OTel spans + metrics on")
    print("every scenario run, proof verification, and canonical-form")
    print("encoding. Wire ``setup_otel(otlp_endpoint=...)`` once at app")
    print("startup and every Ophamin call from then on populates your")
    print("Jaeger / Datadog / Prometheus / Grafana backend.")
    print()
    print("This walkthrough captures the spans + metrics through OTel's")
    print("InMemoryExporter so you can see exactly what Ophamin emits.")

    # === Step 1: install in-memory OTel providers ===
    print("\n## Step 1: install in-memory OTel providers")
    handles = _install_in_memory_otel()
    span_exporter: InMemorySpanExporter = handles["span_exporter"]  # type: ignore[assignment]
    metric_reader: InMemoryMetricReader = handles["metric_reader"]  # type: ignore[assignment]
    print(f"  service name:        {DEFAULT_SERVICE_NAME}")
    print(f"  instrumentation:     {INSTRUMENTATION_NAME} v{__version__}")
    print(f"  span exporter:       {type(span_exporter).__name__}")
    print(f"  metric reader:       {type(metric_reader).__name__}")

    # === Step 2: exercise verify_proof_impl to emit a span ===
    proofs = sorted(PROOFS_DIR.rglob("*.json"))
    if not proofs:
        raise SystemExit("No shipped proofs found under proofs/measurement_machinery/")
    proof_path = proofs[0]

    print(f"\n## Step 2: verify a proof (emits `ophamin.proof.verify` span)")
    print(f"  proof: {proof_path.name}")
    result = verify_proof_impl(proof_path.read_text())
    print(f"  verified:        {result['verified']}")
    print(f"  verdict.outcome: {result['verdict']['outcome']}")

    # === Step 3: exercise canonicalize_value_impl to emit a span ===
    print(f"\n## Step 3: canonicalize a value (emits `ophamin.canonical.encode` span)")
    canonicalize_value_impl(json.dumps({"a": 1, "b": 2.5}))
    canonicalize_value_impl(json.dumps([1, 2, 3, 4, 5]))
    print("  emitted two canonical-encode spans")

    # === Step 4: inspect captured spans ===
    print("\n## Step 4: captured spans")
    spans = list(span_exporter.get_finished_spans())
    print(f"  total spans captured: {len(spans)}")
    print()
    print(f"  {'name':<32} {'status':<8} attributes")
    print(f"  {'-' * 32} {'-' * 8} {'-' * 50}")
    for span in spans:
        attrs = dict(span.attributes or {})
        attr_pairs = ", ".join(
            f"{k}={v}" for k, v in sorted(attrs.items()) if k.startswith("ophamin.")
        )
        print(f"  {span.name:<32} {span.status.status_code.name:<8} {attr_pairs[:80]}")

    # === Step 5: inspect captured metrics ===
    print("\n## Step 5: captured metrics")
    metric_data = metric_reader.get_metrics_data()
    if metric_data is None or not metric_data.resource_metrics:
        print("  (no metrics emitted at this point — metrics flush periodically)")
    else:
        for rm in metric_data.resource_metrics:
            for sm in rm.scope_metrics:
                for metric in sm.metrics:
                    print(f"  metric: {metric.name}")
                    for point in metric.data.data_points:
                        value = getattr(point, "value", getattr(point, "sum", None))
                        print(f"    value: {value}")

    # === Invariants — what we MUST pin ===
    assert len(spans) >= 3, "Should have at least 3 spans (1 verify + 2 canonicalize)"
    span_names = {s.name for s in spans}
    assert "ophamin.proof.verify" in span_names
    assert "ophamin.canonical.encode" in span_names

    # Find the verify span and assert its attributes
    verify_spans = [s for s in spans if s.name == "ophamin.proof.verify"]
    assert len(verify_spans) >= 1
    verify_attrs = dict(verify_spans[0].attributes or {})
    assert verify_attrs.get("ophamin.proof.verified") is True

    print("\n✓ OpenTelemetry walkthrough complete. Contract validated.")


if __name__ == "__main__":
    main()
