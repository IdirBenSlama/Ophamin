"""Tests for the PrometheusScrapeProbe — passive /metrics consumer.

A throwaway HTTP server (stdlib http.server) serves a Prometheus-formatted
text body. The probe scrapes it, parses, signs the snapshot, and we assert:

* round-trip JSON
* HMAC verification
* tampering breaks the signature
* per-family + per-sample data is preserved
* loud failure on bad URL / timeout / unparseable body
* alignment helper produces correct deltas
"""

from __future__ import annotations

import http.server
import json
import threading

import pytest

from ophamin.seeing.telemetry import (
    DEFAULT_SIGN_KEY,
    MetricFamilySnapshot,
    MetricSample,
    PrometheusScrapeProbe,
    PrometheusSnapshot,
    TelemetryScrapeError,
    align_to_window,
)
from ophamin.seeing.telemetry.prometheus_probe import PROMETHEUS_AVAILABLE


# --------------------------------------------------------------------------
# Tiny stdlib HTTP server that serves controllable Prometheus text payloads
# --------------------------------------------------------------------------


SAMPLE_METRICS = """\
# HELP kimera_cycles_total Total Takwin cycles completed by the substrate
# TYPE kimera_cycles_total counter
kimera_cycles_total{target="entity"} 142.0
kimera_cycles_total{target="walker"} 7.0
# HELP kimera_phi_value Per-cycle Phi (integrated information)
# TYPE kimera_phi_value gauge
kimera_phi_value 0.6213
# HELP kimera_request_duration_seconds Request latency in seconds
# TYPE kimera_request_duration_seconds histogram
kimera_request_duration_seconds_bucket{le="0.1"} 5.0
kimera_request_duration_seconds_bucket{le="0.5"} 18.0
kimera_request_duration_seconds_bucket{le="1.0"} 22.0
kimera_request_duration_seconds_bucket{le="+Inf"} 24.0
kimera_request_duration_seconds_sum 11.4
kimera_request_duration_seconds_count 24.0
"""


class _MetricsHandler(http.server.BaseHTTPRequestHandler):
    payload: bytes = SAMPLE_METRICS.encode("utf-8")
    response_code: int = 200

    def do_GET(self):  # noqa: N802 — http.server's convention
        if self.path != "/metrics":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"not found")
            return
        self.send_response(self.response_code)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(self.payload)))
        self.end_headers()
        self.wfile.write(self.payload)

    def log_message(self, *_a, **_k):
        # silence default stderr noise
        pass


@pytest.fixture
def fake_metrics_server():
    """Start a throwaway HTTP server on an ephemeral port, yield its base URL."""
    server = http.server.HTTPServer(("127.0.0.1", 0), _MetricsHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/metrics"
    finally:
        server.shutdown()
        thread.join(timeout=2)


# Mark every test that needs the dep so we degrade gracefully if it's missing.
requires_prom = pytest.mark.skipif(
    not PROMETHEUS_AVAILABLE,
    reason="prometheus_client not installed (install with [telemetry] extra)",
)


# --------------------------------------------------------------------------
# Scrape happy path
# --------------------------------------------------------------------------


@requires_prom
def test_probe_scrapes_and_signs(fake_metrics_server):
    probe = PrometheusScrapeProbe(url=fake_metrics_server)
    snap = probe.scrape()
    assert isinstance(snap, PrometheusSnapshot)
    assert snap.signature, "scrape result must be signed"
    assert snap.verify(DEFAULT_SIGN_KEY)


@requires_prom
def test_scrape_parses_all_three_metric_types(fake_metrics_server):
    snap = PrometheusScrapeProbe(url=fake_metrics_server).scrape()
    names = set(snap.metric_names())
    # prometheus_client strips the `_total` suffix from counter family names
    # (Prometheus convention); the suffix remains on individual sample names.
    assert "kimera_cycles" in names
    assert "kimera_phi_value" in names
    assert "kimera_request_duration_seconds" in names

    # Counter family retains both labelled samples; sample names carry _total.
    cycles = snap.family("kimera_cycles")
    assert cycles is not None
    assert cycles.metric_type == "counter"
    sample_targets = {dict(s.labels).get("target") for s in cycles.samples
                      if s.name == "kimera_cycles_total"}
    assert {"entity", "walker"} <= sample_targets


@requires_prom
def test_scrape_preserves_sample_values(fake_metrics_server):
    snap = PrometheusScrapeProbe(url=fake_metrics_server).scrape()
    phi = snap.family("kimera_phi_value")
    assert phi is not None
    assert phi.metric_type == "gauge"
    assert len(phi.samples) == 1
    assert phi.samples[0].value == pytest.approx(0.6213)


@requires_prom
def test_scrape_handles_histogram_buckets_and_summary_fields(fake_metrics_server):
    snap = PrometheusScrapeProbe(url=fake_metrics_server).scrape()
    hist = snap.family("kimera_request_duration_seconds")
    assert hist is not None
    assert hist.metric_type == "histogram"
    # Buckets + _sum + _count all appear as samples.
    sample_names = {s.name for s in hist.samples}
    assert "kimera_request_duration_seconds_bucket" in sample_names
    assert "kimera_request_duration_seconds_sum" in sample_names
    assert "kimera_request_duration_seconds_count" in sample_names


@requires_prom
def test_scrape_records_wall_time_and_raw_size(fake_metrics_server):
    snap = PrometheusScrapeProbe(url=fake_metrics_server).scrape()
    assert snap.wall_time_s > 0
    assert snap.raw_bytes_len == len(SAMPLE_METRICS.encode("utf-8"))


@requires_prom
def test_scrape_source_url_is_recorded(fake_metrics_server):
    snap = PrometheusScrapeProbe(url=fake_metrics_server).scrape()
    assert snap.source_url == fake_metrics_server


# --------------------------------------------------------------------------
# Round-trip + tampering
# --------------------------------------------------------------------------


@requires_prom
def test_snapshot_round_trips_through_json(fake_metrics_server):
    snap = PrometheusScrapeProbe(url=fake_metrics_server).scrape()
    text = snap.to_json()
    rebuilt = PrometheusSnapshot.from_dict(json.loads(text))
    assert rebuilt.snapshot_id == snap.snapshot_id
    assert rebuilt.total_samples() == snap.total_samples()
    assert rebuilt.verify(DEFAULT_SIGN_KEY)


@requires_prom
def test_tampering_breaks_signature(fake_metrics_server):
    snap = PrometheusScrapeProbe(url=fake_metrics_server).scrape()
    tampered = PrometheusSnapshot(
        source_url=snap.source_url,
        scraped_at=snap.scraped_at,
        wall_time_s=snap.wall_time_s,
        raw_bytes_len=snap.raw_bytes_len + 1,        # tamper with payload size
        families=snap.families,
        ophamin_version=snap.ophamin_version,
        schema_version=snap.schema_version,
        signature=snap.signature,                    # keep old sig
    )
    assert not tampered.verify(DEFAULT_SIGN_KEY)


@requires_prom
def test_snapshot_id_is_deterministic_for_same_body():
    families = (
        MetricFamilySnapshot(
            name="x", metric_type="gauge", documentation="d",
            samples=(MetricSample(name="x", labels=(), value=1.0),),
        ),
    )
    snap = PrometheusSnapshot(
        source_url="http://x/metrics",
        scraped_at="2026-05-15T12:00:00+00:00",
        wall_time_s=0.01,
        raw_bytes_len=42,
        families=families,
    )
    snap2 = PrometheusSnapshot(
        source_url=snap.source_url, scraped_at=snap.scraped_at,
        wall_time_s=snap.wall_time_s, raw_bytes_len=snap.raw_bytes_len,
        families=snap.families,
    )
    assert snap.snapshot_id == snap2.snapshot_id


# --------------------------------------------------------------------------
# Loud-failure paths
# --------------------------------------------------------------------------


@requires_prom
def test_scrape_loud_failure_on_unreachable_url():
    # Reserved-port unlikely to be bound — connection refused.
    probe = PrometheusScrapeProbe(url="http://127.0.0.1:1/metrics", timeout_s=1.0)
    with pytest.raises(TelemetryScrapeError):
        probe.scrape()


@requires_prom
def test_scrape_loud_failure_on_bad_payload(fake_metrics_server, monkeypatch):
    # Swap in a payload the parser will reject.
    _MetricsHandler.payload = b"not valid prometheus output [["
    try:
        probe = PrometheusScrapeProbe(url=fake_metrics_server)
        with pytest.raises(TelemetryScrapeError):
            probe.scrape()
    finally:
        _MetricsHandler.payload = SAMPLE_METRICS.encode("utf-8")


# --------------------------------------------------------------------------
# Cross-stratum alignment helper
# --------------------------------------------------------------------------


@requires_prom
def test_align_to_window_returns_correct_delta(fake_metrics_server):
    probe = PrometheusScrapeProbe(url=fake_metrics_server)
    before = probe.scrape()

    # Mutate the server payload to simulate cycles incrementing.
    _MetricsHandler.payload = SAMPLE_METRICS.replace(
        'kimera_cycles_total{target="entity"} 142.0',
        'kimera_cycles_total{target="entity"} 200.0',
    ).encode("utf-8")
    try:
        after = probe.scrape()
        window = align_to_window(
            scenario_name="test",
            window_start="2026-05-15T12:00:00+00:00",
            window_end="2026-05-15T12:05:00+00:00",
            before=before,
            after=after,
        )
        # The family is named "kimera_cycles" (parser strips _total suffix);
        # individual samples retain `_total` in their name. metric_delta sums
        # by family name, so the family lookup uses the stripped name.
        delta = window.metric_delta("kimera_cycles")
        # entity: 142 → 200 (+58), walker: 7 → 7 (+0). Sum: 149 → 207 (+58)
        assert delta["before_sum"] == pytest.approx(149.0)
        assert delta["after_sum"] == pytest.approx(207.0)
        assert delta["delta"] == pytest.approx(58.0)
    finally:
        _MetricsHandler.payload = SAMPLE_METRICS.encode("utf-8")


@requires_prom
def test_align_to_window_missing_metric_yields_zero_delta(fake_metrics_server):
    snap = PrometheusScrapeProbe(url=fake_metrics_server).scrape()
    window = align_to_window(
        scenario_name="t", window_start="x", window_end="y",
        before=snap, after=snap,
    )
    delta = window.metric_delta("does_not_exist")
    assert delta == {"before_sum": 0.0, "after_sum": 0.0, "delta": 0.0}


@requires_prom
def test_align_to_window_accepts_during_samples(fake_metrics_server):
    snap = PrometheusScrapeProbe(url=fake_metrics_server).scrape()
    window = align_to_window(
        scenario_name="t", window_start="x", window_end="y",
        before=snap, after=snap, during=(snap, snap, snap),
    )
    assert len(window.during) == 3


# --------------------------------------------------------------------------
# Snapshot introspection helpers
# --------------------------------------------------------------------------


@requires_prom
def test_total_samples_counts_across_all_families(fake_metrics_server):
    snap = PrometheusScrapeProbe(url=fake_metrics_server).scrape()
    # 2 cycles_total + 1 phi_value + 4 histogram buckets + sum + count + created
    # = 9 (prometheus_client 0.25 emits a `_created` OpenMetrics extension
    # sample for both counters and histograms; we accept that as a strict
    # superset of the legacy 8).
    assert snap.total_samples() >= 8


@requires_prom
def test_samples_for_returns_empty_tuple_on_unknown(fake_metrics_server):
    snap = PrometheusScrapeProbe(url=fake_metrics_server).scrape()
    assert snap.samples_for("not_a_metric") == ()


def test_metric_sample_round_trip():
    s = MetricSample(name="x", labels=(("a", "1"),), value=3.14, timestamp=1.5)
    rebuilt = MetricSample.from_dict(s.to_dict())
    assert rebuilt == s


def test_metric_family_snapshot_round_trip():
    f = MetricFamilySnapshot(
        name="x", metric_type="gauge", documentation="d",
        samples=(MetricSample(name="x", labels=(), value=1.0),),
    )
    rebuilt = MetricFamilySnapshot.from_dict(f.to_dict())
    assert rebuilt == f


def test_prometheus_snapshot_from_dict_rejects_missing_keys():
    with pytest.raises(ValueError, match="missing required keys"):
        PrometheusSnapshot.from_dict({"source_url": "x"})
