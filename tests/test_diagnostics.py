"""Tests for the substrate-specific cognitive diagnostics.

Conformal prediction is cross-checked against MAPIE driven directly; cognitive
inertia and the kernel-coupling diagnostic are framework-defined and tested
behaviourally.
"""

import numpy as np
import pytest
from mapie.regression import SplitConformalRegressor
from sklearn.linear_model import LinearRegression

from ophamin.measuring.pillars.diagnostics.anticipatory import (
    KNOWN_FAILURE,
    OOD_ANOMALY,
    AnticipatoryFailureClassifier,
    ConformalPredictor,
)
from ophamin.measuring.pillars.diagnostics.inertia import CognitiveInertiaMeter
from ophamin.measuring.pillars.diagnostics.kernel_coupling import (
    INTRINSIC_EXPLORATION,
    MISCALIBRATED_BOUNDARY_LOGIC,
    NO_COLLAPSE,
    OracleKernelCouplingDiagnostic,
)
from ophamin.seeing.substrate.mock import MockSubstrate


def _conformal_data(seed: int = 0, n: int = 400):
    rng = np.random.default_rng(seed)
    X = rng.normal(0.0, 1.0, (n, 2))
    y = 2.0 * X[:, 0] + X[:, 1] + rng.normal(0.0, 0.5, n)
    return X, y


# -- conformal prediction (MAPIE-backed) -----------------------------------

def test_conformal_predictor_meets_coverage_guarantee():
    X, y = _conformal_data()
    cp = ConformalPredictor(confidence_level=0.9).calibrate(
        X[:300], y[:300], random_state=0
    )
    coverage = cp.coverage(X[300:], y[300:])
    assert coverage >= 0.85  # MAPIE's finite-sample guarantee at level 0.9


def test_conformal_predictor_matches_mapie_directly():
    X, y = _conformal_data()
    cp = ConformalPredictor(confidence_level=0.9).calibrate(
        X[:300], y[:300], random_state=0, calibration_fraction=0.4
    )
    pred, lo, hi = cp.predict_interval(X[300:])
    # cross-check: drive MAPIE with the SAME train/calibration split
    perm = np.random.default_rng(0).permutation(300)
    n_cal = max(2, int(round(0.4 * 300)))
    cal_idx, train_idx = perm[:n_cal], perm[n_cal:]
    scr = SplitConformalRegressor(
        estimator=LinearRegression(), confidence_level=0.9, prefit=False
    )
    scr.fit(X[:300][train_idx], y[:300][train_idx])
    scr.conformalize(X[:300][cal_idx], y[:300][cal_idx])
    ref_pred, ref_int = scr.predict_interval(X[300:])
    assert np.allclose(pred, np.asarray(ref_pred).ravel(), rtol=1e-6)
    assert np.allclose(lo, np.asarray(ref_int)[:, 0, 0], rtol=1e-6)
    assert np.allclose(hi, np.asarray(ref_int)[:, 1, 0], rtol=1e-6)


def test_conformal_requires_calibration():
    with pytest.raises(RuntimeError):
        ConformalPredictor().predict_interval([[1.0, 2.0]])


# -- anticipatory failure classification -----------------------------------

def test_anticipatory_classifier_and_world_model_gap():
    X, y = _conformal_data()
    cp = ConformalPredictor(confidence_level=0.9).calibrate(
        X[:300], y[:300], random_state=0
    )
    clf = AnticipatoryFailureClassifier(cp)
    for i in range(300, 360):  # well-covered outcomes
        clf.assess(X[i], y[i])
    clf.assess(X[360], y[360], known_failure_signal=True)  # a known failure
    clf.assess(X[361], y[361] + 50.0)  # an outcome far outside the interval

    report = clf.report()
    assert report.n_assessed == 62
    assert report.observed_counts.get(OOD_ANOMALY, 0) >= 1  # the +50 breach
    assert report.confusion.get((KNOWN_FAILURE, KNOWN_FAILURE), 0) == 1
    assert 0.0 <= report.world_model_gap <= 1.0
    assert 0.0 <= report.empirical_miscoverage <= 1.0


# -- cognitive inertia (framework-defined metric) --------------------------

def test_inertia_zero_when_substrate_updates_fully():
    meter = CognitiveInertiaMeter()
    for _ in range(10):
        meter.observe(evidence_strength=1.0, expected_shift=1.0, observed_shift=1.0)
    report = meter.report()
    assert report.inertia_index == pytest.approx(0.0)
    assert report.bayesian_adaptation_rate == pytest.approx(1.0)


def test_inertia_one_when_substrate_never_updates():
    meter = CognitiveInertiaMeter()
    for _ in range(10):
        meter.observe(evidence_strength=1.0, expected_shift=1.0, observed_shift=0.0)
    report = meter.report()
    assert report.inertia_index == pytest.approx(1.0)
    assert report.stagnant


def test_inertia_tracks_defensive_rejection_rate():
    meter = CognitiveInertiaMeter()
    for i in range(10):
        meter.observe(1.0, 1.0, 0.5, accepted=(i % 2 == 0))
    assert meter.report().defensive_rejection_rate == pytest.approx(0.5)


# -- oracle kernel-coupling diagnostic -------------------------------------

def test_kernel_coupling_isolates_miscalibrated_boundary():
    sut = MockSubstrate(seed=1, collapse_cells=["BAD"], collapse_entropy_below=0.02)
    diag = OracleKernelCouplingDiagnostic(
        entropy_coefficients=[0.005, 0.01, 0.05, 0.20], n_reps=5
    )
    result = diag.sweep(sut, cells=["BAD", "GOOD"])
    assert result.verdict_for("BAD") == MISCALIBRATED_BOUNDARY_LOGIC
    assert result.verdict_for("GOOD") == NO_COLLAPSE


def test_kernel_coupling_isolates_intrinsic_collapse():
    sut = MockSubstrate(seed=1, collapse_cells=["BAD"], collapse_entropy_below=1.0)
    diag = OracleKernelCouplingDiagnostic(
        entropy_coefficients=[0.005, 0.01, 0.05, 0.20], n_reps=5
    )
    assert diag.sweep(sut, cells=["BAD"]).verdict_for("BAD") == INTRINSIC_EXPLORATION
