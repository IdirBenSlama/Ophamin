"""Tests for OpenTelemetry instrumentation of Ophamin's read + run + verify.

Uses OTel's ``InMemorySpanExporter`` and ``InMemoryMetricReader`` to
capture the spans + metrics emitted by Ophamin's shared
implementations. The tests then assert per-span attributes + metric
records match the documented instrumentation contract.

When no OTel SDK provider is configured (the production default),
the spans + metrics are no-ops; the **shape** of the no-op path is
exercised by :class:`TestNoOpPath`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
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
    run_scenario_impl,
    verify_proof_impl,
)
from ophamin.observability import (
    DEFAULT_SERVICE_NAME,
    INSTRUMENTATION_NAME,
    INSTRUMENTATION_VERSION,
    OphaminInstrumentor,
    get_meter,
    get_tracer,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
PROOFS_DIR = REPO_ROOT / "proofs" / "measurement_machinery"
ANY_SHIPPED_PROOF = next(PROOFS_DIR.rglob("*.json"), None)


# --------------------------------------------------------------------------
# Fixtures — set up an in-memory OTel exporter for each test that needs
# to observe what spans / metrics get emitted.
# --------------------------------------------------------------------------


@pytest.fixture
def otel_in_memory(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Install in-memory OTel providers + return the exporters.

    Returns a dict with keys ``span_exporter`` and ``metric_reader``.
    Tests inspect ``span_exporter.get_finished_spans()`` and
    ``metric_reader.get_metrics_data()`` to verify what was emitted.

    Implementation note: OTel's ``set_tracer_provider`` and
    ``set_meter_provider`` are one-shot globals. For test isolation
    we monkeypatch :func:`ophamin.observability.otel.get_tracer` and
    :func:`ophamin.observability.otel.get_meter` to return per-test
    providers without touching the global state. Then we reset the
    :class:`OphaminInstrumentor` singleton so it rebuilds its
    instruments against the test providers.
    """
    span_exporter = InMemorySpanExporter()
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(span_exporter))

    metric_reader = InMemoryMetricReader()
    meter_provider = MeterProvider(metric_readers=[metric_reader])

    def fake_get_tracer() -> trace.Tracer:
        return tracer_provider.get_tracer("ophamin", __version__)

    def fake_get_meter() -> metrics.Meter:
        return meter_provider.get_meter("ophamin", __version__)

    monkeypatch.setattr(
        "ophamin.observability.otel.get_tracer", fake_get_tracer
    )
    monkeypatch.setattr(
        "ophamin.observability.otel.get_meter", fake_get_meter
    )

    # Reset the OphaminInstrumentor singleton so it picks up our
    # in-memory providers when it constructs its instruments.
    OphaminInstrumentor.reset()

    yield {
        "span_exporter": span_exporter,
        "metric_reader": metric_reader,
        "tracer_provider": tracer_provider,
        "meter_provider": meter_provider,
    }

    # Cleanup — reset the singleton so subsequent tests get fresh
    # instruments against whatever provider is current.
    OphaminInstrumentor.reset()
    tracer_provider.shutdown()
    meter_provider.shutdown()


# --------------------------------------------------------------------------
# Constants / accessor tests (no provider needed)
# --------------------------------------------------------------------------


class TestConstants:
    def test_default_service_name(self) -> None:
        assert DEFAULT_SERVICE_NAME == "ophamin"

    def test_instrumentation_name(self) -> None:
        assert INSTRUMENTATION_NAME == "ophamin"

    def test_instrumentation_version_matches_framework(self) -> None:
        assert INSTRUMENTATION_VERSION == __version__


class TestNoOpPath:
    """When no SDK provider is configured, instrumentation is a no-op.

    The shape of the no-op path matters: calling the shared impls
    must produce identical functional output regardless of whether
    OTel is configured.
    """

    def test_get_tracer_returns_proxy_when_no_sdk(self) -> None:
        OphaminInstrumentor.reset()
        t = get_tracer()
        assert t is not None
        # No-op tracer accepts start_as_current_span without raising.
        with t.start_as_current_span("test"):
            pass

    def test_get_meter_returns_proxy_when_no_sdk(self) -> None:
        OphaminInstrumentor.reset()
        m = get_meter()
        assert m is not None
        counter = m.create_counter("test_counter")
        # add() on a no-op counter is a no-op.
        counter.add(1, attributes={"a": "b"})


# --------------------------------------------------------------------------
# Verify-proof instrumentation
# --------------------------------------------------------------------------


class TestVerifyProofInstrumentation:
    @pytest.mark.skipif(
        ANY_SHIPPED_PROOF is None,
        reason="no shipped signed proofs found in the repo",
    )
    def test_verify_emits_span(self, otel_in_memory: dict[str, Any]) -> None:
        text = ANY_SHIPPED_PROOF.read_text(encoding="utf-8")
        result = verify_proof_impl(text)
        assert result["verified"] is True

        spans = otel_in_memory["span_exporter"].get_finished_spans()
        verify_spans = [s for s in spans if s.name == "ophamin.proof.verify"]
        assert verify_spans, (
            f"expected ophamin.proof.verify span; got {[s.name for s in spans]}"
        )
        s = verify_spans[-1]
        attrs = dict(s.attributes or {})
        assert attrs.get("ophamin.proof.verified") is True
        assert attrs.get("ophamin.verdict.outcome") in (
            "VALIDATED", "REFUTED", "INCONCLUSIVE",
        )
        assert isinstance(attrs.get("ophamin.proof.id"), str)
        assert len(attrs["ophamin.proof.id"]) == 64

    @pytest.mark.skipif(
        ANY_SHIPPED_PROOF is None, reason="no shipped proofs",
    )
    def test_tampered_proof_sets_span_status_error(
        self, otel_in_memory: dict[str, Any]
    ) -> None:
        from opentelemetry.trace import StatusCode

        text = ANY_SHIPPED_PROOF.read_text(encoding="utf-8")
        record = json.loads(text)
        sig = record["signature"]
        record["signature"] = ("1" if sig[0] == "0" else "0") + sig[1:]
        verify_proof_impl(json.dumps(record))

        spans = otel_in_memory["span_exporter"].get_finished_spans()
        verify_spans = [s for s in spans if s.name == "ophamin.proof.verify"]
        assert verify_spans
        s = verify_spans[-1]
        # Span status set to ERROR on signature mismatch.
        assert s.status.status_code == StatusCode.ERROR
        # The result still surfaces verified=False (NOT an exception);
        # span IS marked ERROR for observability purposes.

    @pytest.mark.skipif(
        ANY_SHIPPED_PROOF is None, reason="no shipped proofs",
    )
    def test_verify_increments_counter(self, otel_in_memory: dict[str, Any]) -> None:
        text = ANY_SHIPPED_PROOF.read_text(encoding="utf-8")
        verify_proof_impl(text)
        data = otel_in_memory["metric_reader"].get_metrics_data()
        names = {
            m.name
            for rm in data.resource_metrics
            for sm in rm.scope_metrics
            for m in sm.metrics
        }
        assert "ophamin_proofs_verified_total" in names


# --------------------------------------------------------------------------
# Canonicalize instrumentation
# --------------------------------------------------------------------------


class TestCanonicalizeInstrumentation:
    def test_canonicalize_emits_span_with_byte_length(
        self, otel_in_memory: dict[str, Any]
    ) -> None:
        result = canonicalize_value_impl(json.dumps({"x": 30, "y": 30.0}))
        spans = otel_in_memory["span_exporter"].get_finished_spans()
        enc_spans = [s for s in spans if s.name == "ophamin.canonical.encode"]
        assert enc_spans
        attrs = dict(enc_spans[-1].attributes or {})
        assert attrs.get("ophamin.canonical.bytes") == result["canonical_bytes_len"]

    def test_canonicalize_records_byte_histogram(
        self, otel_in_memory: dict[str, Any]
    ) -> None:
        canonicalize_value_impl(json.dumps({"a": 1}))
        data = otel_in_memory["metric_reader"].get_metrics_data()
        names = {
            m.name
            for rm in data.resource_metrics
            for sm in rm.scope_metrics
            for m in sm.metrics
        }
        assert "ophamin_canonical_bytes_encoded" in names


# --------------------------------------------------------------------------
# Run-scenario instrumentation
# --------------------------------------------------------------------------


class TestRunScenarioInstrumentation:
    def test_run_scenario_emits_span(self, otel_in_memory: dict[str, Any]) -> None:
        result = run_scenario_impl(
            "spearman-crosscheck",
            json.dumps({"n_pairs": 3, "sample_size": 20}),
        )
        assert result["verdict"]["outcome"] == "VALIDATED"

        spans = otel_in_memory["span_exporter"].get_finished_spans()
        scenario_spans = [
            s for s in spans if s.name.startswith("ophamin.scenario.run")
        ]
        assert scenario_spans
        s = scenario_spans[-1]
        assert s.name == "ophamin.scenario.run.spearman-crosscheck"
        attrs = dict(s.attributes or {})
        assert attrs.get("ophamin.scenario.name") == "spearman-crosscheck"
        assert attrs.get("ophamin.scenario.family") == "cross_framework"
        assert attrs.get("ophamin.verdict.outcome") == "VALIDATED"
        assert isinstance(attrs.get("ophamin.proof.id"), str)
        assert len(attrs["ophamin.proof.id"]) == 64

    def test_run_scenario_records_metrics(
        self, otel_in_memory: dict[str, Any]
    ) -> None:
        run_scenario_impl(
            "spearman-crosscheck",
            json.dumps({"n_pairs": 3, "sample_size": 20}),
        )
        data = otel_in_memory["metric_reader"].get_metrics_data()
        names = {
            m.name
            for rm in data.resource_metrics
            for sm in rm.scope_metrics
            for m in sm.metrics
        }
        assert "ophamin_scenarios_run_total" in names
        assert "ophamin_scenario_duration_seconds" in names


class TestInstrumentationFreeFromBehavioralDrift:
    """Adding OTel instrumentation MUST NOT change the result of any
    transport-agnostic impl. This test pins the shape contract.
    """

    @pytest.mark.skipif(
        ANY_SHIPPED_PROOF is None, reason="no shipped proofs",
    )
    def test_verify_result_shape_unchanged_with_otel(
        self, otel_in_memory: dict[str, Any]
    ) -> None:
        text = ANY_SHIPPED_PROOF.read_text(encoding="utf-8")
        with_otel = verify_proof_impl(text)
        assert with_otel["verified"] is True
        # Every field that existed pre-0.20.0 still present.
        for k in (
            "verified",
            "proof_id",
            "schema_version",
            "verdict",
            "claim_statement",
            "framework_versions",
        ):
            assert k in with_otel
