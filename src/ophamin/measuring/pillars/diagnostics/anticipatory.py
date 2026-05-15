"""Anticipatory Failure Classification — the world-model gap.

Post-hoc anomaly detection (reacting after a failure) is insufficient for a
substrate with a generative world-model backbone. The framework classifies an
*impending* trajectory as one of:

    SUCCESS        predicted to complete normally
    KNOWN_FAILURE  matches a supervised, previously-characterised failure mode
    OOD_ANOMALY    out-of-distribution — the world model's calibrated interval
                   failed to cover the observed outcome

Conformal prediction is delegated to **MAPIE** (`SplitConformalRegressor`), the
standard Python conformal-prediction library, which gives a finite-sample
coverage guarantee at the chosen ``confidence_level``. The conformal model *is*
the world model: an observed outcome falling outside its interval is, by
construction, something the model did not anticipate.

The *world-model gap* is the rate at which the pre-execution prediction
(supervised) disagrees with the post-execution observation (supervised +
conformal coverage).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
from mapie.regression import SplitConformalRegressor
from sklearn.linear_model import LinearRegression

SUCCESS = "success"
KNOWN_FAILURE = "known_failure"
OOD_ANOMALY = "ood_anomaly"


class ConformalPredictor:
    """Split conformal prediction over (features -> outcome), backed by MAPIE.

    ``calibrate(X, y)`` splits the data, fits the estimator on the training
    part and conformalises on the calibration part. An outcome later observed
    outside ``predict_interval``'s band for its features is out-of-distribution.
    """

    def __init__(self, estimator: Any = None, confidence_level: float = 0.9) -> None:
        if not (0.0 < confidence_level < 1.0):
            raise ValueError("confidence_level must be in (0, 1)")
        self.confidence_level = float(confidence_level)
        self._estimator = estimator if estimator is not None else LinearRegression()
        self._scr: SplitConformalRegressor | None = None

    @staticmethod
    def _as_2d(X) -> np.ndarray:
        X = np.asarray(X, dtype=float)
        return X.reshape(-1, 1) if X.ndim == 1 else X

    def calibrate(
        self,
        X,
        y,
        calibration_fraction: float = 0.4,
        random_state: int | None = None,
    ) -> "ConformalPredictor":
        X = self._as_2d(X)
        y = np.asarray(y, dtype=float).ravel()
        if X.shape[0] != y.shape[0]:
            raise ValueError("X and y must have the same number of rows")
        if X.shape[0] < 8:
            raise ValueError("conformal calibration needs at least 8 samples")
        if not (0.0 < calibration_fraction < 1.0):
            raise ValueError("calibration_fraction must be in (0, 1)")
        n = X.shape[0]
        perm = np.random.default_rng(random_state).permutation(n)
        n_cal = max(2, int(round(calibration_fraction * n)))
        cal_idx, train_idx = perm[:n_cal], perm[n_cal:]
        if len(train_idx) < 2:
            raise ValueError("not enough samples left for the training split")
        scr = SplitConformalRegressor(
            estimator=self._estimator,
            confidence_level=self.confidence_level,
            prefit=False,
        )
        scr.fit(X[train_idx], y[train_idx])
        scr.conformalize(X[cal_idx], y[cal_idx])
        self._scr = scr
        return self

    def _require(self) -> SplitConformalRegressor:
        if self._scr is None:
            raise RuntimeError("ConformalPredictor.calibrate must be called first")
        return self._scr

    def predict_interval(self, X) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return ``(point_prediction, lower, upper)`` arrays for the rows of X."""
        scr = self._require()
        y_pred, y_int = scr.predict_interval(self._as_2d(X))
        y_pred = np.asarray(y_pred, dtype=float).ravel()
        y_int = np.asarray(y_int, dtype=float)
        return y_pred, y_int[:, 0, 0], y_int[:, 1, 0]

    def is_conforming(self, X, y_observed) -> np.ndarray:
        """Boolean array — is each observed outcome inside its conformal interval?"""
        _, lower, upper = self.predict_interval(X)
        y_observed = np.asarray(y_observed, dtype=float).ravel()
        return (y_observed >= lower) & (y_observed <= upper)

    def coverage(self, X, y) -> float:
        """Empirical coverage on a held-out set — for validating the guarantee."""
        return float(np.mean(self.is_conforming(X, y)))


@dataclass
class AnticipatoryReport:
    """The world-model gap after a batch of assessed trajectories."""

    n_assessed: int
    predicted_counts: dict[str, int] = field(default_factory=dict)
    observed_counts: dict[str, int] = field(default_factory=dict)
    confusion: dict[tuple[str, str], int] = field(default_factory=dict)
    world_model_gap: float = 0.0          # fraction where predicted != observed
    empirical_miscoverage: float = 0.0    # fraction of outcomes outside the interval
    world_model_mae: float = 0.0          # mean abs prediction error
    missed_failures: int = 0              # predicted SUCCESS, observed a failure
    false_alarms: int = 0                 # predicted a failure, observed SUCCESS

    def summary(self) -> str:
        return (
            f"anticipatory: n={self.n_assessed} "
            f"world_model_gap={self.world_model_gap:.3f} "
            f"miscoverage={self.empirical_miscoverage:.3f} "
            f"mae={self.world_model_mae:.4g} "
            f"missed_failures={self.missed_failures} false_alarms={self.false_alarms}"
        )


class AnticipatoryFailureClassifier:
    """Three-way classification + world-model-gap tracking, on a ConformalPredictor."""

    def __init__(
        self,
        conformal: ConformalPredictor,
        known_failure_classifier: Callable[[Any], bool] | None = None,
    ) -> None:
        self.conformal = conformal
        self.known_failure_classifier = known_failure_classifier or (lambda _f: False)
        self._predicted: list[str] = []
        self._observed: list[str] = []
        self._abs_errors: list[float] = []

    def assess(
        self,
        features,
        observed_outcome: float,
        known_failure_signal: bool | None = None,
    ) -> str:
        """Classify one trajectory; returns the *pre-execution* predicted class.

        ``known_failure_signal`` overrides the supervised classifier when given.
        The observed class (supervised + conformal coverage) is recorded for the
        world-model-gap report.
        """
        X = np.asarray(features, dtype=float).reshape(1, -1)
        y_pred, lower, upper = self.conformal.predict_interval(X)
        observed = float(observed_outcome)
        known_fail = (
            bool(known_failure_signal)
            if known_failure_signal is not None
            else bool(self.known_failure_classifier(features))
        )

        # predicted, before execution: the supervised signal is all that is known
        predicted = KNOWN_FAILURE if known_fail else SUCCESS

        # observed, after execution: supervised failure, or a conformal-coverage breach
        inside = lower[0] <= observed <= upper[0]
        if known_fail:
            observed_class = KNOWN_FAILURE
        elif not inside:
            observed_class = OOD_ANOMALY
        else:
            observed_class = SUCCESS

        self._predicted.append(predicted)
        self._observed.append(observed_class)
        self._abs_errors.append(abs(observed - float(y_pred[0])))
        return predicted

    def report(self) -> AnticipatoryReport:
        n = len(self._observed)
        if n == 0:
            return AnticipatoryReport(n_assessed=0)
        failure_labels = {KNOWN_FAILURE, OOD_ANOMALY}
        confusion: dict[tuple[str, str], int] = {}
        mismatches = missed = false_alarms = miscovered = 0
        for pred, obs in zip(self._predicted, self._observed):
            confusion[(pred, obs)] = confusion.get((pred, obs), 0) + 1
            if pred != obs:
                mismatches += 1
            if pred == SUCCESS and obs in failure_labels:
                missed += 1
            if pred in failure_labels and obs == SUCCESS:
                false_alarms += 1
            if obs == OOD_ANOMALY:
                miscovered += 1
        return AnticipatoryReport(
            n_assessed=n,
            predicted_counts=dict(Counter(self._predicted)),
            observed_counts=dict(Counter(self._observed)),
            confusion=confusion,
            world_model_gap=mismatches / n,
            empirical_miscoverage=miscovered / n,
            world_model_mae=float(np.mean(self._abs_errors)),
            missed_failures=missed,
            false_alarms=false_alarms,
        )
