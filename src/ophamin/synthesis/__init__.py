"""I pillar — Iterative cumulative synthesis.

Synthesises results across successive iterations to progressively narrow
uncertainty.

    CumulativeMetaAnalysis   sequential pooling of (effect, variance) pairs,
                             fixed- or random-effects, with a two-stage
                             tau^2-freezing option.
"""

from ophamin.synthesis.cma import CMAResult, CumulativeMetaAnalysis

__all__ = ["CMAResult", "CumulativeMetaAnalysis"]
