"""Tests for comparing/drift_detection — River-backed StreamDriftDetector."""

from __future__ import annotations

import json
import random

import pytest

from ophamin.comparing.drift_detection import (
    DEFAULT_SIGN_KEY,
    DriftEvent,
    DriftScan,
    StreamDriftDetector,
    available_detectors,
    detector_factory,
    extract_phi_stream,
    extract_walker_halt_counts,
)
from ophamin.seeing.substrate.base import CycleResult


# --------------------------------------------------------------------------
# Detector availability / factory
# --------------------------------------------------------------------------


def test_available_detectors_includes_river_three():
    avail = available_detectors()
    assert "adwin" in avail
    assert "kswin" in avail
    assert "page_hinkley" in avail


def test_detector_factory_constructs_each_detector():
    for name in ("adwin", "ADWIN", "kswin", "page-hinkley", "page_hinkley"):
        det = detector_factory(name)
        assert det is not None


def test_detector_factory_rejects_unknown_name():
    with pytest.raises(ValueError, match="unknown drift detector"):
        detector_factory("nonexistent_detector")


def test_detector_factory_forwards_kwargs():
    # ADWIN accepts a ``delta`` parameter.
    det = detector_factory("adwin", delta=0.01)
    # We don't introspect the value — just confirm construction succeeded
    # with the kwarg accepted.
    assert det is not None


# --------------------------------------------------------------------------
# Stream extractors
# --------------------------------------------------------------------------


def _cr(idx: int, *, success: bool = True, raw: dict | None = None,
        halt_mode: str | None = None) -> CycleResult:
    return CycleResult(
        cycle_index=idx, success=success,
        raw=raw or {}, halt_mode=halt_mode,
    )


def test_extract_phi_stream_picks_phi_value():
    crs = [
        _cr(0, raw={"phi_value": 0.5}),
        _cr(1, raw={"phi_value": 0.7}),
        _cr(2, raw={"phi_value": 0.6}),
    ]
    stream = extract_phi_stream(crs)
    assert stream == (0.5, 0.7, 0.6)


def test_extract_phi_stream_falls_back_to_kii_value():
    crs = [_cr(0, raw={"kii_value": 0.42})]
    stream = extract_phi_stream(crs)
    assert stream == (0.42,)


def test_extract_phi_stream_skips_unsuccessful_cycles():
    crs = [
        _cr(0, success=True, raw={"phi_value": 0.5}),
        _cr(1, success=False, raw={"phi_value": 0.99}),
        _cr(2, success=True, raw={"phi_value": 0.6}),
    ]
    stream = extract_phi_stream(crs)
    assert stream == (0.5, 0.6)


def test_extract_phi_stream_skips_missing_phi():
    crs = [
        _cr(0, raw={"phi_value": 0.5}),
        _cr(1, raw={"other_field": 99}),
        _cr(2, raw={"phi_value": 0.6}),
    ]
    stream = extract_phi_stream(crs)
    assert stream == (0.5, 0.6)


def test_extract_phi_stream_handles_non_numeric_phi_gracefully():
    crs = [
        _cr(0, raw={"phi_value": 0.5}),
        _cr(1, raw={"phi_value": "not_a_number"}),
        _cr(2, raw={"phi_value": 0.6}),
    ]
    stream = extract_phi_stream(crs)
    assert stream == (0.5, 0.6)


def test_extract_walker_halt_counts_returns_rolling_fraction():
    halts = ["exhausted"] * 8 + ["amplitude_death"] * 4 + ["exhausted"] * 8
    crs = [_cr(i, halt_mode=h) for i, h in enumerate(halts)]
    stream = extract_walker_halt_counts(crs, window=4)
    # First window: 0/4 amplitude_death; final window: 0/4 again. Middle
    # window should be all-amplitude_death = 1.0.
    assert stream[0] == 0.0
    assert max(stream) == 1.0
    assert stream[-1] == 0.0


def test_extract_walker_halt_counts_returns_empty_on_too_few_samples():
    crs = [_cr(0, halt_mode="exhausted")]
    assert extract_walker_halt_counts(crs, window=20) == ()


def test_extract_walker_halt_counts_rejects_zero_window():
    crs = [_cr(i, halt_mode="exhausted") for i in range(10)]
    assert extract_walker_halt_counts(crs, window=0) == ()


# --------------------------------------------------------------------------
# StreamDriftDetector — happy path
# --------------------------------------------------------------------------


def test_scan_on_stationary_stream_fires_few_events():
    """ADWIN on a constant stream should not fire."""
    rng = random.Random(0)
    stream = [0.5 + rng.gauss(0, 0.01) for _ in range(200)]
    detector = StreamDriftDetector("adwin", stream_name="phi_value")
    scan = detector.scan(stream)
    assert isinstance(scan, DriftScan)
    assert scan.n_samples == 200
    # ADWIN false-positive ceiling on tight noise: expect ≤ 2
    assert scan.n_events <= 2


def test_scan_on_step_change_stream_fires_at_step():
    """Stream that changes mean halfway through should fire ADWIN."""
    rng = random.Random(0)
    pre = [0.2 + rng.gauss(0, 0.01) for _ in range(100)]
    post = [0.8 + rng.gauss(0, 0.01) for _ in range(100)]
    stream = pre + post
    detector = StreamDriftDetector("adwin", stream_name="phi_value")
    scan = detector.scan(stream)
    assert scan.n_events >= 1
    # The first event should land near the boundary (sample 100). ADWIN's
    # convergence isn't immediate; allow [100, 130].
    assert any(100 <= e.sample_index <= 130 for e in scan.events), \
        f"events at {[e.sample_index for e in scan.events]} did not " \
        f"include any near the step at 100"


def test_scan_signs_and_verifies():
    detector = StreamDriftDetector("adwin", stream_name="x")
    scan = detector.scan([0.5] * 50)
    assert scan.signature
    assert scan.verify(DEFAULT_SIGN_KEY)


def test_scan_round_trips_through_json():
    detector = StreamDriftDetector("adwin", stream_name="x")
    scan = detector.scan([0.1, 0.2, 0.9, 0.9, 0.9] * 20)
    text = scan.to_json()
    rebuilt = DriftScan.from_dict(json.loads(text))
    assert rebuilt.scan_id == scan.scan_id
    assert rebuilt.n_events == scan.n_events
    assert rebuilt.verify(DEFAULT_SIGN_KEY)


def test_scan_id_is_deterministic_for_same_stream():
    """Two scans of the same stream + same detector + same config should
    produce the same canonical body (modulo the captured_at timestamp)."""
    s1 = StreamDriftDetector("adwin", stream_name="x").scan([0.5] * 30)
    s2 = StreamDriftDetector("adwin", stream_name="x").scan([0.5] * 30)
    assert s1.stream_hash == s2.stream_hash
    assert s1.events == s2.events


def test_scan_tampering_breaks_signature():
    scan = StreamDriftDetector("adwin", stream_name="x").scan([0.5] * 30)
    tampered = DriftScan(
        detector_name=scan.detector_name,
        detector_config=scan.detector_config,
        stream_name=scan.stream_name,
        n_samples=scan.n_samples + 1,        # tamper
        stream_hash=scan.stream_hash,
        events=scan.events,
        captured_at=scan.captured_at,
        ophamin_version=scan.ophamin_version,
        ophamin_git_commit=scan.ophamin_git_commit,
        schema_version=scan.schema_version,
        signature=scan.signature,            # keep old sig
    )
    assert not tampered.verify(DEFAULT_SIGN_KEY)


def test_scan_loud_failure_on_non_numeric_stream():
    """The contract is numeric streams; loud-fail on any other type."""
    detector = StreamDriftDetector("adwin", stream_name="x")
    with pytest.raises(ValueError, match="numeric stream values"):
        detector.scan([0.5, 0.6, "not_a_number", 0.7])


def test_scan_with_kswin_detector():
    """KSWIN should also work — covers a second detector backend."""
    rng = random.Random(0)
    pre = [0.2 + rng.gauss(0, 0.01) for _ in range(100)]
    post = [0.8 + rng.gauss(0, 0.01) for _ in range(100)]
    detector = StreamDriftDetector("kswin", stream_name="x")
    scan = detector.scan(pre + post)
    # KSWIN parameters default conservatively; just assert no crash + signed
    assert scan.signature
    assert scan.verify(DEFAULT_SIGN_KEY)


def test_scan_with_page_hinkley_detector():
    detector = StreamDriftDetector("page_hinkley", stream_name="x")
    scan = detector.scan([0.5] * 100 + [0.9] * 100)
    assert scan.signature


# --------------------------------------------------------------------------
# DriftEvent + DriftScan structure
# --------------------------------------------------------------------------


def test_drift_event_to_dict():
    e = DriftEvent(sample_index=42, detector_name="adwin",
                   value_at_event=0.7, detail={"k": "v"})
    d = e.to_dict()
    assert d == {"sample_index": 42, "detector_name": "adwin",
                 "value_at_event": 0.7, "detail": {"k": "v"}}


def test_drift_scan_event_indices_property():
    detector = StreamDriftDetector("adwin", stream_name="x")
    scan = detector.scan([0.1] * 50 + [0.9] * 50)
    assert scan.event_indices == tuple(e.sample_index for e in scan.events)


def test_drift_scan_fired_property():
    s_no = StreamDriftDetector("adwin", stream_name="x").scan([0.5] * 20)
    assert s_no.fired == (s_no.n_events > 0)


def test_drift_scan_from_dict_rejects_missing_keys():
    with pytest.raises(ValueError, match="missing required keys"):
        DriftScan.from_dict({"detector_name": "adwin"})


# --------------------------------------------------------------------------
# Detector kwargs forwarding
# --------------------------------------------------------------------------


def test_detector_kwargs_persisted_in_scan_config():
    detector = StreamDriftDetector("adwin", stream_name="x", delta=0.001)
    scan = detector.scan([0.5] * 30)
    assert scan.detector_config == {"delta": 0.001}
