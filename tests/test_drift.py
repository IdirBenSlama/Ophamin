"""Tests for the O-pillar drift module (river-backed)."""

import numpy as np
import pytest

from ophamin.observability.drift import DriftMonitor


def test_adwin_detects_a_known_change_point():
    rng = np.random.default_rng(0)
    stream = list(rng.normal(0.0, 1.0, 300)) + list(rng.normal(6.0, 1.0, 300))
    monitor = DriftMonitor("adwin")
    monitor.update_many(stream)
    report = monitor.report()
    assert report.drift_detected
    # ADWIN flags the change shortly after the true shift at index 300
    assert any(290 <= cp <= 370 for cp in report.change_points)


def test_no_drift_on_a_stationary_stream():
    rng = np.random.default_rng(1)
    monitor = DriftMonitor("adwin")
    monitor.update_many(rng.normal(0.0, 1.0, 500))
    assert not monitor.report().drift_detected


def test_ddm_binary_detector_on_error_stream():
    monitor = DriftMonitor("ddm")
    monitor.update_many([0] * 250 + [1] * 250)  # error rate jumps
    assert monitor.report().drift_detected


def test_binary_detector_rejects_non_binary_input():
    monitor = DriftMonitor("ddm")
    with pytest.raises(ValueError):
        monitor.update(0.5)


def test_unknown_detector_raises():
    with pytest.raises(ValueError):
        DriftMonitor("not_a_detector")


def test_reset_clears_state():
    monitor = DriftMonitor("adwin")
    monitor.update_many(list(np.random.default_rng(0).normal(0.0, 1.0, 50)))
    monitor.reset()
    assert monitor.report().n_observations == 0
    assert not monitor.report().drift_detected
