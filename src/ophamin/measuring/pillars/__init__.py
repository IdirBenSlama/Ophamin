"""The six analytic pillars — every Ophamin pillar delegates to a mature,
library-backed implementation rather than rolling its own statistics.

  observability   SPC + SRM + drift detection      (scipy, river)
  adaptive        anytime-valid inference          (statsmodels, confseq)
  effects         mixed-effects + MEA              (statsmodels)
  synthesis       cumulative meta-analysis         (statsmodels)
  robustness      cross-validation                 (scikit-learn)
  diagnostics     anticipatory / inertia / kernel  (MAPIE)

Each pillar exposes a ``Pillar`` protocol implementation (see
``ophamin.protocols.Pillar``); the protocol declares the plug-in surface so
new pillars can register without modifying scenarios.
"""

from __future__ import annotations

from ophamin.measuring.pillars import (
    adaptive,
    diagnostics,
    effects,
    observability,
    robustness,
    synthesis,
)

__all__ = [
    "adaptive",
    "diagnostics",
    "effects",
    "observability",
    "robustness",
    "synthesis",
]
