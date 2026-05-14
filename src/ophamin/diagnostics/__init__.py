"""Substrate-specific cognitive diagnostics.

Beyond the six general pillars, a cognitive / substrate-first system needs
bespoke probes of its biological limits and decision-making.

    anticipatory     Anticipatory Failure Classification (the world-model gap)
    inertia          Cognitive Inertia Metrics (the immune-system gap)
    kernel_coupling  Oracle Kernel-Coupling Diagnostic (variable isolation)
"""

from ophamin.diagnostics.anticipatory import (
    KNOWN_FAILURE,
    OOD_ANOMALY,
    SUCCESS,
    AnticipatoryFailureClassifier,
    AnticipatoryReport,
    ConformalPredictor,
)
from ophamin.diagnostics.inertia import CognitiveInertiaMeter, InertiaReport
from ophamin.diagnostics.kernel_coupling import (
    INTRINSIC_EXPLORATION,
    MISCALIBRATED_BOUNDARY_LOGIC,
    NO_COLLAPSE,
    CellSweep,
    KernelCouplingResult,
    OracleKernelCouplingDiagnostic,
    default_collapse_signal,
)

__all__ = [
    # anticipatory
    "ConformalPredictor",
    "AnticipatoryFailureClassifier",
    "AnticipatoryReport",
    "SUCCESS",
    "KNOWN_FAILURE",
    "OOD_ANOMALY",
    # inertia
    "CognitiveInertiaMeter",
    "InertiaReport",
    # kernel coupling
    "OracleKernelCouplingDiagnostic",
    "KernelCouplingResult",
    "CellSweep",
    "default_collapse_signal",
    "INTRINSIC_EXPLORATION",
    "MISCALIBRATED_BOUNDARY_LOGIC",
    "NO_COLLAPSE",
]
