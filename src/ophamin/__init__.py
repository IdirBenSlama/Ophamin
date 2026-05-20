"""Ophamin — an empirical observatory around Kimera-SWM.

The name is the angelic order **Ophanim** (wheels-within-wheels covered with
eyes — Ezekiel 1:18). Architecturally, Ophamin is a *dyson sphere* around
Kimera: Kimera sits at the centre emitting; Ophamin envelops, senses, and
returns measurement to the operator. Not a tool next to Kimera — a structure
around it.

The structure has **six wheels**, in two concentric triads:

    Outer (empirical) triad:
      seeing       Wheel 1 — how the observatory senses Kimera and the world
                   (substrate, corpus, discovery)
      measuring    Wheel 2 — pre-registered measurement engines + plug-in pillars
                   (proof, scenarios, metrics, pillars.{observability, adaptive,
                   effects, synthesis, robustness, diagnostics})
      comparing    Wheel 3 — cross-Kimera-commit retrospection
                   (drift, provenance, orchestration)

    Inner (engineering) triad:
      instrumenting  Wheel 4 — per-cycle CPU / RSS / page-fault sampling
                     (psutil, opentelemetry, py-spy, memray)
      auditing       Wheel 5 — orchestrated static-analysis tools
                     (ruff, bandit, mypy, pip-audit)
      reporting      Wheel 6 — render results to Markdown / HTML / LaTeX
                     (matplotlib, jinja2)

The six **plug-in pillars** (O · F · A · M · I · N) live inside the
``measuring`` ring:

    O  observability       SPC + SRM + drift detectors      (scipy, river)
    F  formal provenance   PROV-O graph + lineage store     (prov, MLflow, DVC)
    A  adaptive testing    SPRT + mSPRT anytime-valid       (statsmodels)
    M  mixed-effects       MixedLM + MEA                    (statsmodels)
    I  iterative synthesis cumulative meta-analysis         (statsmodels)
    N  n-fold robustness   cross-validation                 (scikit-learn)

The framework is independent of any particular substrate-under-test;
``MockSubstrate`` makes the whole observatory runnable with no external
system, and ``KimeraAdapter`` plugs in Kimera-SWM via a subprocess boundary.
"""

__version__ = "0.64.0"

from ophamin.measuring.metrics.tiers import (
    MetricBundle,
    Tier1Metrics,
    Tier2Metrics,
    Tier3Metrics,
)
from ophamin.measuring.proof.record import (
    Claim,
    EmpiricalProofRecord,
    PillarEvidence,
    PreRegistration,
    Threshold,
    Verdict,
)
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest

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
