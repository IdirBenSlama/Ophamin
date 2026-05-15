"""O pillar — Observability and anomaly detection.

Guarantees the integrity of the measurement pipeline before the substrate's
outputs are evaluated.

    spc    Shewhart control charts (X-bar/R, individuals) + Western Electric rules
    srm    Sample Ratio Mismatch detection (scipy chi-squared goodness of fit)
    drift  concept / data drift detection (river streaming detectors)
"""

from ophamin.measuring.pillars.observability.drift import DriftMonitor, DriftReport
from ophamin.measuring.pillars.observability.spc import (
    ControlChartResult,
    IndividualsChart,
    Violation,
    XbarRChart,
    western_electric_rules,
)
from ophamin.measuring.pillars.observability.srm import SRMDetector, SRMResult

__all__ = [
    "ControlChartResult",
    "IndividualsChart",
    "Violation",
    "XbarRChart",
    "western_electric_rules",
    "SRMDetector",
    "SRMResult",
    "DriftMonitor",
    "DriftReport",
]
