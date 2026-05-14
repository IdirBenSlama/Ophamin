"""Concept / data drift detection (O pillar).

The report devotes a section to concept drift and data drift (covariate shift):
the statistical properties of a stream changing over time, silently degrading a
baseline or a predictive model. This module wraps **river** — the standard
Python library for online drift detection — behind a uniform ``DriftMonitor``.

    numeric streams : ADWIN, KSWIN, Page-Hinkley   (feed the metric value)
    binary streams  : DDM, EDDM                    (feed 0/1 error indicators)

Binary detectors also expose a *warning* zone — an early heads-up before a
confirmed change point.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from river import drift as _river_drift

_NUMERIC = {
    "adwin": _river_drift.ADWIN,
    "kswin": _river_drift.KSWIN,
    "page_hinkley": _river_drift.PageHinkley,
}
_BINARY = {
    "ddm": _river_drift.binary.DDM,
    "eddm": _river_drift.binary.EDDM,
}
_DETECTORS = {**_NUMERIC, **_BINARY}


@dataclass
class DriftReport:
    """Summary of a drift-monitoring pass over a stream."""

    detector: str
    n_observations: int
    n_drifts: int
    change_points: list[int] = field(default_factory=list)
    warning_points: list[int] = field(default_factory=list)

    @property
    def drift_detected(self) -> bool:
        return self.n_drifts > 0

    def summary(self) -> str:
        verdict = "DRIFT" if self.drift_detected else "stable"
        cps = ", ".join(str(c) for c in self.change_points[:8])
        more = " ..." if len(self.change_points) > 8 else ""
        return (
            f"drift[{verdict}] via {self.detector}: {self.n_drifts} change point(s) "
            f"over {self.n_observations} obs"
            + (f" at [{cps}{more}]" if self.change_points else "")
        )


class DriftMonitor:
    """Streaming drift detector — a uniform wrapper over river's detectors.

    ``detector`` is one of: ``adwin``, ``kswin``, ``page_hinkley`` (numeric
    streams) or ``ddm``, ``eddm`` (binary 0/1 error streams). Extra keyword
    arguments are passed straight through to the river detector.
    """

    def __init__(self, detector: str = "adwin", **detector_kwargs) -> None:
        key = detector.lower()
        if key not in _DETECTORS:
            raise ValueError(
                f"unknown drift detector {detector!r}; choose from {sorted(_DETECTORS)}"
            )
        self.detector_name = key
        self.is_binary = key in _BINARY
        self._detector_kwargs = dict(detector_kwargs)
        self._detector = _DETECTORS[key](**detector_kwargs)
        self._n = 0
        self._change_points: list[int] = []
        self._warning_points: list[int] = []

    def update(self, value: float) -> bool:
        """Feed one observation; return whether a change point fired at this step."""
        if self.is_binary and value not in (0, 1, 0.0, 1.0, True, False):
            raise ValueError(
                f"{self.detector_name} is a binary detector — feed 0/1 error indicators"
            )
        self._detector.update(value)
        index = self._n
        self._n += 1
        detected = bool(getattr(self._detector, "drift_detected", False))
        if detected:
            self._change_points.append(index)
        if bool(getattr(self._detector, "warning_detected", False)):
            self._warning_points.append(index)
        return detected

    def update_many(self, values) -> "DriftMonitor":
        for v in values:
            self.update(v)
        return self

    @property
    def drift_detected(self) -> bool:
        return len(self._change_points) > 0

    @property
    def change_points(self) -> list[int]:
        return list(self._change_points)

    def report(self) -> DriftReport:
        return DriftReport(
            detector=self.detector_name,
            n_observations=self._n,
            n_drifts=len(self._change_points),
            change_points=list(self._change_points),
            warning_points=list(self._warning_points),
        )

    def reset(self) -> None:
        self._detector = _DETECTORS[self.detector_name](**self._detector_kwargs)
        self._n = 0
        self._change_points.clear()
        self._warning_points.clear()
