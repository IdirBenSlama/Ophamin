"""Ophamin — an empirical framework for scaling and verifying iterative experimentation.

Six pillars (O-F-A-M-I-N):

    O  observability       observability.spc, observability.srm
    F  formal provenance   provenance.prov, provenance.lineage
    A  adaptive testing    adaptive.sprt
    M  mixed-effects       effects.mixed_effects, effects.mea
    I  iterative synthesis synthesis.cma
    N  n-fold robustness   robustness.cross_validation

The framework is independent of any particular system. The thing it tests is a
``SubstrateUnderTest`` (substrate.base); ``MockSubstrate`` makes the whole
framework runnable with no external system, and ``KimeraAdapter`` plugs in
Kimera-SWM via a subprocess boundary.
"""

__version__ = "0.1.0"

from ophamin.metrics.tiers import MetricBundle, Tier1Metrics, Tier2Metrics, Tier3Metrics
from ophamin.proof.record import (
    Claim,
    EmpiricalProofRecord,
    PillarEvidence,
    PreRegistration,
    Threshold,
    Verdict,
)
from ophamin.substrate.base import CycleResult, SubstrateUnderTest

__all__ = [
    "__version__",
    "MetricBundle",
    "Tier1Metrics",
    "Tier2Metrics",
    "Tier3Metrics",
    "CycleResult",
    "SubstrateUnderTest",
    "EmpiricalProofRecord",
    "Claim",
    "Threshold",
    "PreRegistration",
    "PillarEvidence",
    "Verdict",
]
