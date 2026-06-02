"""PrometheusScrapeProbe — passive consumer of Kimera-SWM's /metrics endpoint.

Kimera already exports metrics via ``prometheus_client.start_http_server`` (see
``kimera_swm/infrastructure/monitoring/prometheus_exporter.py``, default port
9090). This module is the consumer side: it fetches ``/metrics``, parses the
Prometheus text-exposition format, and returns a frozen, content-addressed,
HMAC-signed ``PrometheusSnapshot``.

Three reasons to be a consumer rather than a re-implementer:

1. Kimera's metrics are the authoritative observability stream for
   ~20 of the 68 infrastructure subpackages (per
   ``docs/KIMERA_OBSERVATIONAL_SURFACE_2026_05_15.md`` §4.3). Reading them
   gives Ophamin observability into all of those at once.
2. The text format is standardised (OpenMetrics); a snapshot taken today is
   readable by any Prometheus-compatible tool.
3. Scenarios can stamp the *timestamp window* their cycles ran in, take
   snapshots before / during / after, and feed the triple to the Σ
   correlation pillar without writing any per-metric extraction code.

Loud failure on connectivity errors / timeout / parse failure. Optional
dependency: ``prometheus_client`` is installed with the ``[telemetry]``
extra; absent at import time, the module loads but ``PrometheusScrapeProbe``
construction raises ``TelemetryDependencyMissing``.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

try:
    from prometheus_client.parser import text_string_to_metric_families
    PROMETHEUS_AVAILABLE = True
except ImportError:
    text_string_to_metric_families = None  # type: ignore[assignment]
    PROMETHEUS_AVAILABLE = False


DEFAULT_PROMETHEUS_URL = "http://localhost:9090/metrics"
DEFAULT_SCRAPE_TIMEOUT_S = 5.0
DEFAULT_SIGN_KEY = b"ophamin-telemetry-default-key"
TELEMETRY_SCHEMA_VERSION = 1


class TelemetryDependencyMissing(RuntimeError):
    """Raised when prometheus_client is not installed."""


class TelemetryScrapeError(RuntimeError):
    """Raised when a Prometheus scrape fails — network error, timeout, parse failure."""


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Snapshot data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MetricSample:
    """One Prometheus sample — name + labels + value (+ optional timestamp)."""

    name: str
    labels: tuple[tuple[str, str], ...]   # sorted by key
    value: float
    timestamp: float | None = None        # if the metric carried its own ts

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "labels": list(self.labels),
            "value": self.value,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MetricSample:
        return cls(
            name=str(data["name"]),
            labels=tuple(tuple(lp) for lp in data["labels"]),
            value=float(data["value"]),
            timestamp=(float(data["timestamp"]) if data.get("timestamp") is not None else None),
        )


@dataclass(frozen=True)
class MetricFamilySnapshot:
    """One metric family — name + type + documentation + samples."""

    name: str
    metric_type: str          # "counter" | "gauge" | "histogram" | "summary" | "untyped" | ...
    documentation: str
    samples: tuple[MetricSample, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "metric_type": self.metric_type,
            "documentation": self.documentation,
            "samples": [s.to_dict() for s in self.samples],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MetricFamilySnapshot:
        return cls(
            name=str(data["name"]),
            metric_type=str(data["metric_type"]),
            documentation=str(data.get("documentation", "")),
            samples=tuple(MetricSample.from_dict(s) for s in data["samples"]),
        )

    def sample_count(self) -> int:
        return len(self.samples)


@dataclass(frozen=True)
class PrometheusSnapshot:
    """One complete Prometheus scrape result, signed and content-addressed."""

    source_url: str
    scraped_at: str
    wall_time_s: float                # how long the scrape took
    raw_bytes_len: int                # size of the /metrics response
    families: tuple[MetricFamilySnapshot, ...]
    ophamin_version: str = ""
    schema_version: int = TELEMETRY_SCHEMA_VERSION
    signature: str = ""

    # --- introspection ----------------------------------------------------

    def family(self, name: str) -> MetricFamilySnapshot | None:
        for f in self.families:
            if f.name == name:
                return f
        return None

    def total_samples(self) -> int:
        return sum(f.sample_count() for f in self.families)

    def metric_names(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.families)

    def samples_for(self, metric_name: str) -> tuple[MetricSample, ...]:
        f = self.family(metric_name)
        return f.samples if f is not None else ()

    # --- serialisation + signing ------------------------------------------

    def _body(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "ophamin_version": self.ophamin_version,
            "source_url": self.source_url,
            "scraped_at": self.scraped_at,
            "wall_time_s": self.wall_time_s,
            "raw_bytes_len": self.raw_bytes_len,
            "families": [f.to_dict() for f in self.families],
        }

    def _canonical_bytes(self) -> bytes:
        return json.dumps(self._body(), sort_keys=True, separators=(",", ":")).encode("utf-8")

    @property
    def snapshot_id(self) -> str:
        return hashlib.sha256(self._canonical_bytes()).hexdigest()

    def sign(self, key: bytes) -> PrometheusSnapshot:
        sig = hmac.new(key, self._canonical_bytes(), hashlib.sha256).hexdigest()
        return PrometheusSnapshot(
            source_url=self.source_url,
            scraped_at=self.scraped_at,
            wall_time_s=self.wall_time_s,
            raw_bytes_len=self.raw_bytes_len,
            families=self.families,
            ophamin_version=self.ophamin_version,
            schema_version=self.schema_version,
            signature=sig,
        )

    def verify(self, key: bytes) -> bool:
        if not self.signature:
            return False
        expected = hmac.new(key, self._canonical_bytes(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, self.signature)

    def to_dict(self) -> dict[str, Any]:
        return {"snapshot_id": self.snapshot_id, **self._body(), "signature": self.signature}

    def to_json(self, path: str | None = None, indent: int = 2) -> str:
        from pathlib import Path
        text = json.dumps(self.to_dict(), indent=indent, default=str)
        if path:
            Path(path).write_text(text, encoding="utf-8")
        return text

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PrometheusSnapshot:
        required = {"source_url", "scraped_at", "wall_time_s", "raw_bytes_len", "families"}
        missing = required - set(data)
        if missing:
            raise ValueError(f"PrometheusSnapshot missing required keys: {sorted(missing)}")
        return cls(
            source_url=str(data["source_url"]),
            scraped_at=str(data["scraped_at"]),
            wall_time_s=float(data["wall_time_s"]),
            raw_bytes_len=int(data["raw_bytes_len"]),
            families=tuple(MetricFamilySnapshot.from_dict(f) for f in data["families"]),
            ophamin_version=str(data.get("ophamin_version", "")),
            schema_version=int(data.get("schema_version", TELEMETRY_SCHEMA_VERSION)),
            signature=str(data.get("signature", "")),
        )


# ---------------------------------------------------------------------------
# Probe
# ---------------------------------------------------------------------------


def _parse_prometheus_text(text: str) -> tuple[MetricFamilySnapshot, ...]:
    """Parse Prometheus text-exposition into our frozen snapshot form.

    Uses ``prometheus_client.parser.text_string_to_metric_families``. Loud
    failure if the dep isn't installed.
    """
    if not PROMETHEUS_AVAILABLE:
        raise TelemetryDependencyMissing(
            "prometheus_client is not installed. Install with "
            "`pip install 'ophamin[telemetry]'` to enable the Prometheus probe."
        )
    families: list[MetricFamilySnapshot] = []
    for fam in text_string_to_metric_families(text):
        samples_out: list[MetricSample] = []
        for sample in fam.samples:
            # prometheus_client Sample tuple: (name, labels, value, timestamp, exemplar)
            labels = tuple(sorted((k, str(v)) for k, v in sample.labels.items()))
            ts = sample.timestamp if hasattr(sample, "timestamp") else None
            samples_out.append(MetricSample(
                name=sample.name, labels=labels, value=float(sample.value),
                timestamp=(float(ts) if ts is not None else None),
            ))
        families.append(MetricFamilySnapshot(
            name=fam.name,
            metric_type=fam.type or "untyped",
            documentation=fam.documentation or "",
            samples=tuple(samples_out),
        ))
    return tuple(families)


class PrometheusScrapeProbe:
    """Fetch /metrics from a Prometheus exporter, parse, return a signed snapshot.

    Construction is loud-fail on missing dependency. ``scrape()`` is loud-fail
    on connectivity / timeout / parse error — no silent empty snapshot is
    emitted (would falsely look like a successful "no metrics" run).
    """

    def __init__(
        self,
        url: str = DEFAULT_PROMETHEUS_URL,
        *,
        timeout_s: float = DEFAULT_SCRAPE_TIMEOUT_S,
        sign_key: bytes = DEFAULT_SIGN_KEY,
        ophamin_version: str = "",
    ) -> None:
        if not PROMETHEUS_AVAILABLE:
            raise TelemetryDependencyMissing(
                "prometheus_client is not installed. Install with "
                "`pip install 'ophamin[telemetry]'` to enable the Prometheus probe."
            )
        self.url = url
        self.timeout_s = float(timeout_s)
        self.sign_key = sign_key
        self.ophamin_version = ophamin_version

    def scrape(self) -> PrometheusSnapshot:
        """Fetch /metrics, parse, sign, return a snapshot. Loud failure on error."""
        import time
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(self.url, timeout=self.timeout_s) as resp:  # nosec B310 — configured HTTP(S) endpoint; URL is operator/config-controlled, not user input
                raw = resp.read().decode("utf-8", errors="replace")
        except urllib.error.URLError as e:
            raise TelemetryScrapeError(
                f"failed to scrape {self.url}: {type(e).__name__}: {e}"
            ) from e
        except TimeoutError as e:
            raise TelemetryScrapeError(
                f"scrape of {self.url} timed out after {self.timeout_s}s"
            ) from e

        wall = time.perf_counter() - t0
        try:
            families = _parse_prometheus_text(raw)
        except Exception as e:
            raise TelemetryScrapeError(
                f"failed to parse {self.url} response as Prometheus text: "
                f"{type(e).__name__}: {e}"
            ) from e

        snap = PrometheusSnapshot(
            source_url=self.url,
            scraped_at=_now_utc_iso(),
            wall_time_s=wall,
            raw_bytes_len=len(raw),
            families=families,
            ophamin_version=self.ophamin_version,
        )
        return snap.sign(self.sign_key)


# ---------------------------------------------------------------------------
# Cross-stratum alignment — pair a scrape series with a scenario window
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AlignedTelemetryWindow:
    """A scenario window paired with telemetry snapshots taken before / after.

    Used by the Σ (cross-stratum correlation) measuring pillar to test whether
    cognitive-tier events (Φ drift, walker amplitude_death) correlate with
    telemetry-tier signals (request latency spike, GC pressure, queue depth).
    """

    scenario_name: str
    window_start: str       # UTC ISO timestamp when the scenario began
    window_end: str         # UTC ISO timestamp when the scenario ended
    before: PrometheusSnapshot
    after: PrometheusSnapshot
    during: tuple[PrometheusSnapshot, ...] = ()  # optional mid-window samples

    def metric_delta(self, metric_name: str) -> dict[str, float]:
        """Compute (after_sum - before_sum) for one metric across all samples.

        Returns a dict with ``before_sum``, ``after_sum``, ``delta``. Missing
        metric on either side yields 0.0 sums for that side.
        """
        def _sum(snap: PrometheusSnapshot) -> float:
            return sum(s.value for s in snap.samples_for(metric_name))
        before_sum = _sum(self.before)
        after_sum = _sum(self.after)
        return {
            "before_sum": before_sum,
            "after_sum": after_sum,
            "delta": after_sum - before_sum,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "before": self.before.to_dict(),
            "after": self.after.to_dict(),
            "during": [s.to_dict() for s in self.during],
        }


def align_to_window(
    scenario_name: str,
    window_start: str,
    window_end: str,
    before: PrometheusSnapshot,
    after: PrometheusSnapshot,
    during: Iterable[PrometheusSnapshot] = (),
) -> AlignedTelemetryWindow:
    """Pair before/during/after snapshots with a scenario's run window.

    All timestamps are assumed UTC-ISO; ``window_start`` should be ≤
    ``before.scraped_at`` and ``window_end`` ≥ ``after.scraped_at`` for the
    alignment to be meaningful. The helper does NOT enforce that — the
    pillar consuming this can decide what to do with mis-aligned windows.
    """
    return AlignedTelemetryWindow(
        scenario_name=scenario_name,
        window_start=window_start,
        window_end=window_end,
        before=before,
        after=after,
        during=tuple(during),
    )
