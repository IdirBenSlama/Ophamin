"""StreamDriftDetector — wraps River's drift detectors with signed-record discipline.

Per CLAUDE.md §"loud failure / no silent fallbacks", every drift detection
either fires loudly (with the detected change-point + drift magnitude) or
emits a clean "no drift detected" record. Silent degradation forbidden.

Two streams the substrate emits that drift detection naturally targets:

  extract_phi_stream(cycle_results)
        Per-cycle Φ values. Stationary on engineered axioms (Family E:
        mean 0.621 ± 0.065 across 200 cycles); drifts on adversarial /
        novel content (Family P measured median 0.209 on Linux kernel
        commits, ~3× lower).

  extract_walker_halt_counts(cycle_results)
        Per-cycle walker halt-mode multinomial frequency. Family P
        measured a 3-way split on Linux commits (39.6% exhausted /
        31.5% selective / 28.9% amplitude_death) — drift on this stream
        marks Walker behavior shift.

Detector wrappers expose River's online API (one ``update(value)`` per
sample). DriftScan aggregates the per-step results into a signed record.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from ophamin import __version__
from ophamin.comparing.provenance.lineage import (
    _ophamin_project_root,
    capture_git_commit,
)
from ophamin.seeing.substrate.base import CycleResult


DEFAULT_SIGN_KEY = b"ophamin-drift-default-key"
DRIFT_SCHEMA_VERSION = 1


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Stream extractors — turn CycleResult sequences into 1-D float streams
# ---------------------------------------------------------------------------


#: keys searched in raw, in priority order. Kimera emits "phi_value"
#: (KIMERA_FIELD_CATALOG), MockSubstrate emits "phi", some legacy emits
#: "kii_value" (Kimera's pre-rename). All three are accepted.
_PHI_KEYS = ("phi_value", "phi", "kii_value")


def extract_phi_stream(cycle_results: Iterable[CycleResult]) -> tuple[float, ...]:
    """Per-cycle Φ values. Skips cycles where no recognised Φ key is present.

    Returns a tuple so callers can treat the stream as immutable.
    """
    out: list[float] = []
    for cr in cycle_results:
        if not cr.success:
            continue
        if not isinstance(cr.raw, dict):
            continue
        v = None
        for key in _PHI_KEYS:
            if key in cr.raw:
                v = cr.raw[key]
                break
        if v is None:
            continue
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            continue
    return tuple(out)


def extract_walker_halt_counts(
    cycle_results: Iterable[CycleResult],
    *,
    window: int = 20,
) -> tuple[float, ...]:
    """Rolling fraction of cycles where ``halt_mode == "amplitude_death"``.

    Returns a stream of length ``len(cycles) - window + 1`` (one value per
    sliding window). Drift on this stream marks a shift in Walker M2 firing
    rate — Family E5 reported the rate decays monotonically with substrate
    state accumulation.
    """
    halts = [cr.halt_mode == "amplitude_death" for cr in cycle_results if cr.success]
    if len(halts) < window or window <= 0:
        return ()
    out: list[float] = []
    for i in range(len(halts) - window + 1):
        chunk = halts[i:i + window]
        out.append(sum(chunk) / window)
    return tuple(out)


# ---------------------------------------------------------------------------
# Detector wrapper
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DriftEvent:
    """One detected drift point in a stream."""

    sample_index: int                 # which sample triggered the detector
    detector_name: str                # "ADWIN" | "KSWIN" | "PageHinkley"
    value_at_event: float             # the stream value at the event
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_index": self.sample_index,
            "detector_name": self.detector_name,
            "value_at_event": self.value_at_event,
            "detail": dict(self.detail),
        }


@dataclass(frozen=True)
class DriftScan:
    """A signed, content-addressed result of running one detector over one stream."""

    detector_name: str
    detector_config: dict[str, Any]
    stream_name: str                   # caller-supplied label (e.g. "phi_value")
    n_samples: int
    stream_hash: str                   # SHA-256 of the canonical-bytes stream
    events: tuple[DriftEvent, ...]
    captured_at: str = field(default_factory=_now_utc_iso)
    ophamin_version: str = ""
    ophamin_git_commit: str = ""
    schema_version: int = DRIFT_SCHEMA_VERSION
    signature: str = ""

    @property
    def n_events(self) -> int:
        return len(self.events)

    @property
    def fired(self) -> bool:
        return self.n_events > 0

    @property
    def event_indices(self) -> tuple[int, ...]:
        return tuple(e.sample_index for e in self.events)

    def _body(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "ophamin_version": self.ophamin_version,
            "ophamin_git_commit": self.ophamin_git_commit,
            "captured_at": self.captured_at,
            "detector_name": self.detector_name,
            "detector_config": dict(self.detector_config),
            "stream_name": self.stream_name,
            "n_samples": self.n_samples,
            "stream_hash": self.stream_hash,
            "events": [e.to_dict() for e in self.events],
        }

    def _canonical_bytes(self) -> bytes:
        return json.dumps(self._body(), sort_keys=True, separators=(",", ":")).encode("utf-8")

    @property
    def scan_id(self) -> str:
        return hashlib.sha256(self._canonical_bytes()).hexdigest()

    def sign(self, key: bytes) -> DriftScan:
        sig = hmac.new(key, self._canonical_bytes(), hashlib.sha256).hexdigest()
        return DriftScan(
            detector_name=self.detector_name,
            detector_config=self.detector_config,
            stream_name=self.stream_name,
            n_samples=self.n_samples,
            stream_hash=self.stream_hash,
            events=self.events,
            captured_at=self.captured_at,
            ophamin_version=self.ophamin_version,
            ophamin_git_commit=self.ophamin_git_commit,
            schema_version=self.schema_version,
            signature=sig,
        )

    def verify(self, key: bytes) -> bool:
        if not self.signature:
            return False
        expected = hmac.new(key, self._canonical_bytes(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, self.signature)

    def to_dict(self) -> dict[str, Any]:
        return {"scan_id": self.scan_id, **self._body(), "signature": self.signature}

    def to_json(self, path: str | None = None, indent: int = 2) -> str:
        text = json.dumps(self.to_dict(), indent=indent, default=str)
        if path:
            Path(path).write_text(text, encoding="utf-8")
        return text

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DriftScan:
        required = {"detector_name", "detector_config", "stream_name",
                    "n_samples", "stream_hash", "events"}
        missing = required - set(data)
        if missing:
            raise ValueError(f"DriftScan missing required keys: {sorted(missing)}")
        return cls(
            detector_name=str(data["detector_name"]),
            detector_config=dict(data["detector_config"]),
            stream_name=str(data["stream_name"]),
            n_samples=int(data["n_samples"]),
            stream_hash=str(data["stream_hash"]),
            events=tuple(
                DriftEvent(
                    sample_index=int(e["sample_index"]),
                    detector_name=str(e["detector_name"]),
                    value_at_event=float(e["value_at_event"]),
                    detail=dict(e.get("detail", {})),
                )
                for e in data["events"]
            ),
            captured_at=str(data.get("captured_at", _now_utc_iso())),
            ophamin_version=str(data.get("ophamin_version", "")),
            ophamin_git_commit=str(data.get("ophamin_git_commit", "")),
            schema_version=int(data.get("schema_version", DRIFT_SCHEMA_VERSION)),
            signature=str(data.get("signature", "")),
        )


def _hash_stream(values: tuple[float, ...]) -> str:
    """Stable SHA-256 of a float stream — for content-addressing the scan."""
    canonical = json.dumps(list(values), separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


# ---------------------------------------------------------------------------
# Detector factory
# ---------------------------------------------------------------------------


def available_detectors() -> tuple[str, ...]:
    """Detector names installed in this venv. Currently River-backed."""
    out: list[str] = []
    try:
        from river import drift as _d  # noqa: F401
        out.extend(["adwin", "kswin", "page_hinkley"])
    except ImportError:
        pass
    return tuple(out)


def detector_factory(name: str, **kwargs: Any) -> Any:
    """Construct a River drift detector by name. Loud failure on unknown.

    ``name`` is case-insensitive. ``kwargs`` are forwarded to the River
    detector's constructor — see River docs for ``ADWIN`` / ``KSWIN`` /
    ``PageHinkley`` parameters.
    """
    try:
        from river import drift
    except ImportError as e:
        raise RuntimeError(
            "river is required for drift detection but not installed; "
            "`pip install river`"
        ) from e

    factories: dict[str, Callable[..., Any]] = {
        "adwin": drift.ADWIN,
        "kswin": drift.KSWIN,
        "page_hinkley": drift.PageHinkley,
    }
    norm = name.strip().lower().replace("-", "_")
    if norm not in factories:
        raise ValueError(
            f"unknown drift detector {name!r}; available: {sorted(factories)}"
        )
    return factories[norm](**kwargs)


# ---------------------------------------------------------------------------
# StreamDriftDetector — the wrapping orchestrator
# ---------------------------------------------------------------------------


class StreamDriftDetector:
    """Wraps a River drift detector + emits a signed DriftScan per stream.

    Loud failure on missing river dep. Per-step ``update`` records every
    drift event the underlying detector flags. Final ``finalize`` packages
    the events + stream metadata into a content-addressed signed scan.
    """

    def __init__(
        self,
        detector_name: str = "adwin",
        *,
        stream_name: str = "stream",
        sign_key: bytes = DEFAULT_SIGN_KEY,
        **detector_kwargs: Any,
    ) -> None:
        self.detector_name = detector_name.strip().lower().replace("-", "_")
        self.stream_name = stream_name
        self.sign_key = sign_key
        self.detector_kwargs = detector_kwargs
        self._detector = detector_factory(detector_name, **detector_kwargs)

    def scan(self, stream: Iterable[float]) -> DriftScan:
        """Run the detector over a stream end-to-end. Returns a signed scan."""
        values: list[float] = []
        events: list[DriftEvent] = []
        for i, raw_v in enumerate(stream):
            try:
                v = float(raw_v)
            except (TypeError, ValueError) as e:
                raise ValueError(
                    f"drift detector requires numeric stream values; sample {i} "
                    f"is {type(raw_v).__name__}: {e}"
                ) from e
            values.append(v)
            self._detector.update(v)
            if self._detector.drift_detected:
                events.append(DriftEvent(
                    sample_index=i,
                    detector_name=self.detector_name,
                    value_at_event=v,
                ))

        scan = DriftScan(
            detector_name=self.detector_name,
            detector_config=dict(self.detector_kwargs),
            stream_name=self.stream_name,
            n_samples=len(values),
            stream_hash=_hash_stream(tuple(values)),
            events=tuple(events),
            ophamin_version=__version__,
            ophamin_git_commit=capture_git_commit(_ophamin_project_root()) or "",
        )
        return scan.sign(self.sign_key)
