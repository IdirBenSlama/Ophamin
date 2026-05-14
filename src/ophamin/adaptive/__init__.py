"""A pillar — Adaptive sequential testing.

Replaces fixed-horizon testing with dynamic evaluation that terminates exactly
when statistical certainty is achieved.

    SPRT / GaussianSPRT / BernoulliSPRT   Wald's sequential probability ratio test
    MixtureSPRT                           mSPRT with always-valid (anytime) p-values
"""

from ophamin.adaptive.sprt import (
    ACCEPT_H0,
    ACCEPT_H1,
    CONTINUE,
    REJECT_H0,
    BernoulliSPRT,
    GaussianSPRT,
    MixtureSPRT,
    MixtureSPRTState,
    SPRT,
    SPRTState,
)

__all__ = [
    "ACCEPT_H0",
    "ACCEPT_H1",
    "CONTINUE",
    "REJECT_H0",
    "SPRT",
    "SPRTState",
    "GaussianSPRT",
    "BernoulliSPRT",
    "MixtureSPRT",
    "MixtureSPRTState",
]
