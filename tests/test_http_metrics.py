"""Tests for the 0.61.0 HTTP metrics layer — stateful + stateless gauges.

Pins:
- All MUST-gauge signal names present in render_exposition() output
- Stateful counters survive across calls (HTTP middleware behaviour)
- The middleware tracks routed-path template (low cardinality)
- Scrape-time gauges reflect current ground truth (bundle count etc.)
- record_substrate_batch pulls phi + halt_mode + success correctly
- record_scenario_run + record_scenario_failure + record_render_failure
  update the right counters
- Exposition parses cleanly as Prometheus text format
- /metrics endpoint doesn't inflate its own counter
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from ophamin.http_api.metrics import (
    METRICS,
    OphaminMetrics,
    render_exposition,
)
from ophamin.http_api.server import build_app


@pytest.fixture(autouse=True)
def reset_metrics():
    """Reset the module-level METRICS singleton between tests.

    Without this, counters / histograms / gauges accumulate across the
    whole test session and assertions about "exactly 1.0" become
    order-dependent. prometheus_client stores per-label samples in
    each collector's ``_metrics`` dict — clearing it returns the
    collector to its initial 'no labels seen' state.
    """
    for collector in (
        METRICS.http_requests_total,
        METRICS.http_request_duration_seconds,
        METRICS.scenario_runs_total,
        METRICS.scenario_run_duration_seconds,
        METRICS.scenario_run_failures_total,
        METRICS.proof_render_failures_total,
        METRICS.substrate_cycles_total,
        METRICS.substrate_cycle_duration_seconds,
        METRICS.substrate_cycle_failures_total,
        METRICS.substrate_last_phi,
        METRICS.substrate_halt_reason_total,
    ):
        if hasattr(collector, "_metrics"):
            collector._metrics.clear()
    # in_flight is a Gauge without labels — reset its value directly
    METRICS.http_requests_in_flight._value.set(0)
    yield


@pytest.fixture
def client():
    """A fresh app per test so middleware state stays clean."""
    return TestClient(build_app())


# --------------------------------------------------------------------------
# Required MUST-gauge signal names
# --------------------------------------------------------------------------

EXPECTED_SIGNAL_NAMES = {
    # Framework
    "ophamin_build_info",
    "ophamin_python_runtime_info",
    "ophamin_uptime_seconds",
    "ophamin_health",
    # Scenarios
    "ophamin_scenarios_registered",
    "ophamin_scenarios_registered_by_tier",
    "ophamin_scenarios_registered_by_family",
    "ophamin_scenario_runs_total",
    "ophamin_scenario_run_duration_seconds",
    "ophamin_scenario_run_failures_total",
    # Bundles
    "ophamin_proof_bundles_total",
    "ophamin_proof_bundles_by_tier",
    "ophamin_proof_bundles_by_scenario",
    "ophamin_proof_verdicts",
    "ophamin_proof_bundle_storage_bytes",
    "ophamin_proof_latest_timestamp",
    "ophamin_proof_render_failures_total",
    # HTTP
    "ophamin_http_requests_total",
    "ophamin_http_request_duration_seconds",
    "ophamin_http_requests_in_flight",
    # Process
    "ophamin_process_cpu_seconds_total",
    "ophamin_process_resident_memory_bytes",
    "ophamin_process_threads",
    # Substrate
    "ophamin_substrate_cycles_total",
    "ophamin_substrate_cycle_duration_seconds",
    "ophamin_substrate_cycle_failures_total",
    "ophamin_substrate_last_phi",
    "ophamin_substrate_halt_reason_total",
    # Disk
    "ophamin_disk_free_bytes",
}


def test_all_must_gauge_signals_present():
    body, _ = render_exposition()
    text = body.decode()
    help_lines = [line for line in text.split("\n") if line.startswith("# HELP ")]
    seen = {line.split()[2] for line in help_lines}
    missing = EXPECTED_SIGNAL_NAMES - seen
    assert not missing, f"missing signals: {sorted(missing)}"


def test_exposition_content_type_is_prometheus_text():
    _, ct = render_exposition()
    assert ct.startswith("text/plain")
    assert "version=" in ct


def test_exposition_parses_as_prometheus_text_format():
    body, _ = render_exposition()
    text = body.decode()
    # Each non-comment, non-blank line must be `name[{labels}] value [ts]`
    line_re = re.compile(
        r'^[a-zA-Z_][a-zA-Z0-9_]*'
        r'(?:\{[^}]*\})?'
        r' [\-0-9eE+.NaIinf]+(?:\s+[0-9]+)?$'
    )
    for i, line in enumerate(text.split("\n"), 1):
        if not line.strip() or line.startswith("#"):
            continue
        assert line_re.match(line), f"line {i} does not parse: {line!r}"


def test_exposition_combines_stateful_and_stateless():
    METRICS.http_requests_total.labels(
        method="GET", path="/test/coexist", status="200",
    ).inc()
    body, _ = render_exposition()
    text = body.decode()
    assert "ophamin_http_requests_total" in text
    assert "ophamin_uptime_seconds" in text


# --------------------------------------------------------------------------
# HTTP middleware
# --------------------------------------------------------------------------

def test_middleware_records_request_counter(client):
    client.get("/version")
    body, _ = render_exposition()
    text = body.decode()
    # NB: label values may themselves contain `{` and `}` (e.g. when path
    # carries `{name}`), so [^}]* won't span them. Anchor on `} <value>`.
    assert re.search(
        r'ophamin_http_requests_total\{.*?method="GET".*?path="/version".*?status="200".*?\} \d',
        text,
    )


def test_middleware_skips_metrics_endpoint(client):
    client.get("/metrics")
    client.get("/metrics")
    body, _ = render_exposition()
    text = body.decode()
    assert 'path="/metrics"' not in text


def test_middleware_skips_static_assets(client):
    client.get("/ui/static/styles.css")
    client.get("/ui/static/app.js")
    body, _ = render_exposition()
    text = body.decode()
    assert 'path="/ui/static/' not in text


def test_middleware_uses_routed_path_template(client):
    """Two different concrete URLs that match the same route template
    share ONE label series — bounds Prometheus cardinality."""
    client.get("/scenarios/anova-crosscheck/claim")
    client.get("/scenarios/spearman-crosscheck/claim")
    body, _ = render_exposition()
    text = body.decode()
    assert 'path="/scenarios/{name}/claim"' in text
    assert 'path="/scenarios/anova-crosscheck/claim"' not in text


def test_middleware_records_4xx_status(client):
    client.get("/scenarios/does-not-exist/claim")
    body, _ = render_exposition()
    text = body.decode()
    # Path label contains literal `{name}` — regex anchor on `} <value>`
    # instead of [^}]* (which stops at the embedded `}`).
    assert re.search(
        r'ophamin_http_requests_total\{.*?status="404".*?\} \d',
        text,
    )


# --------------------------------------------------------------------------
# OphaminMetrics convenience hooks
# --------------------------------------------------------------------------

def test_record_scenario_run_increments_counter():
    m = OphaminMetrics()
    m.record_scenario_run(
        scenario_name="test-x", verdict="VALIDATED", duration_seconds=0.5,
    )
    samples = list(m.scenario_runs_total.collect())[0].samples
    assert any(
        s.labels == {"scenario": "test-x", "verdict": "VALIDATED"}
        and s.value == 1.0
        for s in samples
    )


def test_record_scenario_failure_increments_counter():
    m = OphaminMetrics()
    m.record_scenario_failure(scenario_name="x", exception="ValueError")
    samples = list(m.scenario_run_failures_total.collect())[0].samples
    assert any(
        s.labels == {"scenario": "x", "exception": "ValueError"}
        and s.value == 1.0
        for s in samples
    )


def test_record_render_failure_per_format():
    m = OphaminMetrics()
    m.record_render_failure(format_name="pdf")
    samples = list(m.proof_render_failures_total.collect())[0].samples
    assert any(s.labels == {"format": "pdf"} and s.value == 1.0 for s in samples)


def test_record_substrate_batch_pulls_phi_halt_failures():
    from ophamin.seeing.substrate.base import CycleResult
    crs = [
        CycleResult(cycle_index=0, success=True, raw={"phi": 0.7},
                    halt_mode="M1_commit"),
        CycleResult(cycle_index=1, success=True, raw={"phi": 0.62},
                    halt_mode="M2_amplitude_death"),
        CycleResult(cycle_index=2, success=False, raw={},
                    halt_mode="exception",
                    error="TimeoutError: something"),
    ]
    m = OphaminMetrics()
    m.record_substrate_batch(
        substrate_name="mock", cycle_results=crs, batch_duration_seconds=1.5,
    )

    samples = list(m.substrate_cycles_total.collect())[0].samples
    assert any(s.labels == {"substrate": "mock"} and s.value == 3.0 for s in samples)

    samples = list(m.substrate_last_phi.collect())[0].samples
    assert any(s.labels == {"substrate": "mock"} and s.value == 0.62 for s in samples)

    samples = list(m.substrate_cycle_failures_total.collect())[0].samples
    assert any(
        s.labels.get("substrate") == "mock"
        and "TimeoutError" in s.labels.get("kind", "")
        for s in samples
    )

    samples = list(m.substrate_halt_reason_total.collect())[0].samples
    # Counter exposes BOTH `<name>_total` (count) and `<name>_created`
    # (creation timestamp). Filter to just the count rows.
    halt_counts = {
        s.labels["halt"]: s.value
        for s in samples
        if s.labels.get("substrate") == "mock"
        and "halt" in s.labels
        and s.name.endswith("_total")
    }
    assert halt_counts == {
        "M1_commit": 1.0, "M2_amplitude_death": 1.0, "exception": 1.0,
    }


def test_record_substrate_batch_empty_is_noop():
    m = OphaminMetrics()
    m.record_substrate_batch(
        substrate_name="mock", cycle_results=[], batch_duration_seconds=0,
    )
    samples = list(m.substrate_cycles_total.collect())[0].samples
    assert all(s.value == 0.0 for s in samples)


# --------------------------------------------------------------------------
# Scrape-time bundle gauges
# --------------------------------------------------------------------------

def test_bundle_gauges_reflect_disk(tmp_path, monkeypatch):
    bundle = tmp_path / "engineering" / "throughput-ceiling" / \
             "2026-05-19_validated_aaaaaaaaaaaa"
    bundle.mkdir(parents=True)
    (bundle / "proof.json").write_text("{}")
    monkeypatch.setenv("OPHAMIN_PROOFS_ROOT", str(tmp_path))

    body, _ = render_exposition()
    text = body.decode()
    assert "ophamin_proof_bundles_total 1.0" in text
    assert re.search(
        r'ophamin_proof_bundles_by_tier\{tier="engineering"\}\s+1\.0',
        text,
    )
    assert re.search(
        r'ophamin_proof_verdicts\{verdict="validated"\}\s+1\.0',
        text,
    )


def test_health_degrades_when_proofs_root_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("OPHAMIN_PROOFS_ROOT", str(tmp_path / "missing"))
    body, _ = render_exposition()
    assert "ophamin_health 0.0" in body.decode()


def test_uptime_gauge_non_negative():
    body, _ = render_exposition()
    # Anchor on line start so we don't match `# HELP ophamin_uptime_seconds Seconds...`
    m = re.search(r"^ophamin_uptime_seconds (\S+)$", body.decode(), re.MULTILINE)
    assert m and float(m.group(1)) >= 0


def test_process_cpu_increases_after_work():
    body1, _ = render_exposition()
    sum(i * i for i in range(50_000))  # burn some CPU
    body2, _ = render_exposition()
    m1 = re.search(r"^ophamin_process_cpu_seconds_total (\S+)$", body1.decode(), re.MULTILINE)
    m2 = re.search(r"^ophamin_process_cpu_seconds_total (\S+)$", body2.decode(), re.MULTILINE)
    assert m1 and m2 and float(m2.group(1)) >= float(m1.group(1))


# --------------------------------------------------------------------------
# /metrics endpoint integration
# --------------------------------------------------------------------------

def test_metrics_endpoint_returns_combined_output(client):
    client.get("/health")
    client.get("/version")
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "ophamin_uptime_seconds" in r.text             # stateless
    assert "ophamin_http_requests_total" in r.text        # stateful
    assert "ophamin_proof_bundles_total" in r.text        # scrape-time
    assert "ophamin_process_resident_memory_bytes" in r.text


def test_metrics_endpoint_does_not_self_inflate(client):
    for _ in range(5):
        client.get("/metrics")
    body = client.get("/metrics").text
    assert re.search(
        r'ophamin_http_requests_total\{[^}]*path="/metrics"', body,
    ) is None
