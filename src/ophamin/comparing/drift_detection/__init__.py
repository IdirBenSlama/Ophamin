"""comparing/drift_detection/ — per-stream drift detection on Ophamin metrics.

Plug-in adapter pattern (per docs/PLUGIN_CATALOG_2026_05_15.md §22 PR #4).
Today's implementation wraps River's drift detectors (ADWIN, KSWIN,
PageHinkley) since River is already in Ophamin's runtime deps and supports
Python 3.14 (Frouros caps at 3.12, Evidently pulls 19+ extra deps).

Contract: any drift detector wraps the same ``StreamDriftDetector``
interface so future swaps (Frouros once it supports 3.14, custom CUSUM,
TorchDrift kernel-MMD) are mechanical.

The ``DriftScan`` artefact is a frozen, content-addressed, HMAC-signed
record carrying the input stream, the detector configuration, and every
fired drift event. Two scans against the same input + same detector
produce the same scan_id (modulo timestamps).
"""

from ophamin.comparing.drift_detection.river_detector import (
    DEFAULT_SIGN_KEY,
    DriftEvent,
    DriftScan,
    StreamDriftDetector,
    available_detectors,
    detector_factory,
    extract_phi_stream,
    extract_walker_halt_counts,
)

__all__ = [
    "DEFAULT_SIGN_KEY",
    "DriftEvent",
    "DriftScan",
    "StreamDriftDetector",
    "available_detectors",
    "detector_factory",
    "extract_phi_stream",
    "extract_walker_halt_counts",
]
