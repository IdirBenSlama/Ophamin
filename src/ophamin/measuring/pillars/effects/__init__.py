"""M pillar — Mixed-effects and multi-experiment analysis.

Isolates the true causal impact of inputs in environments with overlapping
conditions or longitudinal tracking.

    RandomInterceptModel / center_and_scale   random-intercept linear mixed model
    MultiExperimentAnalysis                   effects under arbitrary overlap
"""

from ophamin.measuring.pillars.effects.mea import (
    Coefficient,
    EffectEstimate,
    InteractionResult,
    JointEstimate,
    MultiExperimentAnalysis,
)
from ophamin.measuring.pillars.effects.mixed_effects import (
    MixedEffectsResult,
    RandomInterceptModel,
    center_and_scale,
)

__all__ = [
    "RandomInterceptModel",
    "MixedEffectsResult",
    "center_and_scale",
    "MultiExperimentAnalysis",
    "EffectEstimate",
    "InteractionResult",
    "JointEstimate",
    "Coefficient",
]
