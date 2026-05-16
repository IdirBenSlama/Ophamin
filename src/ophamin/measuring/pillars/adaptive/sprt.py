"""Adaptive sequential testing — SPRT and the mixture SPRT (A pillar).

Fixed-horizon experiments require all data collected and the timeline expired
before a conclusion can be drawn. Sequential tests evaluate the hypothesis as
each new data point arrives, terminating precisely when statistical certainty
is reached.

    SPRT          Wald's sequential probability ratio test. Accumulates the
                  log-likelihood ratio; crosses an upper bound -> accept H1,
                  lower bound -> accept H0, otherwise continue.

    MixtureSPRT   mSPRT — integrates the likelihood ratio over a mixing
                  distribution on the alternative, yielding "always-valid"
                  (anytime) p-values. A monitor may peek continuously and stop
                  as soon as p crosses the threshold, with no penalty for
                  optional stopping.

References: Wald (1945), Sequential Analysis; Robbins (1970); Johari, Pekelis,
Walsh, "Always Valid Inference" — the mixture LR is a non-negative martingale
under H0, so Ville's inequality gives the anytime guarantee.
"""

from __future__ import annotations

import abc
import math
from dataclasses import dataclass
from typing import Iterable

# decision constants — plain strings keep results JSON-friendly
ACCEPT_H0 = "accept_h0"
ACCEPT_H1 = "accept_h1"
CONTINUE = "continue"
REJECT_H0 = "reject_h0"


@dataclass
class SPRTState:
    """Snapshot of a sequential test after n observations."""

    n: int
    llr: float
    decision: str
    upper: float
    lower: float

    @property
    def terminated(self) -> bool:
        return self.decision != CONTINUE


class SPRT(abc.ABC):
    """Wald's Sequential Probability Ratio Test.

    Subclasses supply the per-observation log-likelihood ratio for a fully
    specified H0 vs H1. Boundaries are derived from the target error rates:

        upper = log((1 - beta) / alpha)
        lower = log(beta / (1 - alpha))
    """

    def __init__(self, alpha: float = 0.05, beta: float = 0.20) -> None:
        if not (0.0 < alpha < 1.0) or not (0.0 < beta < 1.0):
            raise ValueError("alpha and beta must be in (0, 1)")
        self.alpha = float(alpha)
        self.beta = float(beta)
        self.upper = math.log((1.0 - beta) / alpha)
        self.lower = math.log(beta / (1.0 - alpha))
        self._n = 0
        self._llr = 0.0

    @abc.abstractmethod
    def _llr_increment(self, x: float) -> float:
        """Return log f(x | H1) - log f(x | H0) for a single observation."""

    def update(self, x: float) -> str:
        """Feed one observation; return the current decision."""
        self._llr += self._llr_increment(x)
        self._n += 1
        return self.decision

    def update_many(self, xs: "Iterable[float]") -> str:
        for x in xs:
            decision = self.update(x)
            if decision != CONTINUE:
                return decision
        return self.decision

    @property
    def decision(self) -> str:
        if self._llr >= self.upper:
            return ACCEPT_H1
        if self._llr <= self.lower:
            return ACCEPT_H0
        return CONTINUE

    @property
    def n(self) -> int:
        return self._n

    @property
    def llr(self) -> float:
        return self._llr

    def state(self) -> SPRTState:
        return SPRTState(
            n=self._n,
            llr=self._llr,
            decision=self.decision,
            upper=self.upper,
            lower=self.lower,
        )

    def reset(self) -> None:
        self._n = 0
        self._llr = 0.0


class GaussianSPRT(SPRT):
    """SPRT for a Gaussian mean with known variance: H0: mu=mu0 vs H1: mu=mu1."""

    def __init__(
        self, mu0: float, mu1: float, sigma: float, alpha: float = 0.05, beta: float = 0.20
    ) -> None:
        if sigma <= 0:
            raise ValueError("sigma must be positive")
        if mu0 == mu1:
            raise ValueError("mu0 and mu1 must differ for a sequential test")
        super().__init__(alpha=alpha, beta=beta)
        self.mu0 = float(mu0)
        self.mu1 = float(mu1)
        self.sigma = float(sigma)

    def _llr_increment(self, x: float) -> float:
        # [ (x - mu0)^2 - (x - mu1)^2 ] / (2 sigma^2)
        num = (x - self.mu0) ** 2 - (x - self.mu1) ** 2
        return num / (2.0 * self.sigma**2)


class BernoulliSPRT(SPRT):
    """SPRT for a Bernoulli rate: H0: p=p0 vs H1: p=p1."""

    def __init__(
        self, p0: float, p1: float, alpha: float = 0.05, beta: float = 0.20
    ) -> None:
        if not (0.0 < p0 < 1.0) or not (0.0 < p1 < 1.0):
            raise ValueError("p0 and p1 must be in (0, 1)")
        if p0 == p1:
            raise ValueError("p0 and p1 must differ for a sequential test")
        super().__init__(alpha=alpha, beta=beta)
        self.p0 = float(p0)
        self.p1 = float(p1)
        self._log_ratio_1 = math.log(p1 / p0)
        self._log_ratio_0 = math.log((1.0 - p1) / (1.0 - p0))

    def _llr_increment(self, x: float) -> float:
        if x not in (0, 1, 0.0, 1.0, True, False):
            raise ValueError("BernoulliSPRT observations must be 0 or 1")
        xi = 1.0 if x else 0.0
        return xi * self._log_ratio_1 + (1.0 - xi) * self._log_ratio_0


@dataclass
class MixtureSPRTState:
    """Snapshot of a mixture SPRT after n observations."""

    n: int
    mixture_lr: float
    running_max_lr: float
    always_valid_pvalue: float
    decision: str


class MixtureSPRT:
    """Mixture SPRT (mSPRT) with always-valid p-values.

    Tests H0: mean == ``mu0`` for observations of known variance ``sigma**2``,
    against a Gaussian mixture alternative N(mu0, ``tau2``). The mixture
    likelihood ratio after n observations with running mean ``xbar`` is:

        Lambda_n = sqrt(sigma^2 / (sigma^2 + n*tau2))
                   * exp( n^2 * tau2 * (xbar - mu0)^2
                          / (2 * sigma^2 * (sigma^2 + n*tau2)) )

    The always-valid p-value is ``p_n = min(1, 1 / max_{m<=n} Lambda_m)``. It
    may be inspected at every n; ``P(inf_n p_n <= alpha) <= alpha`` under H0.
    """

    def __init__(self, mu0: float = 0.0, sigma: float = 1.0, tau2: float = 1.0) -> None:
        if sigma <= 0:
            raise ValueError("sigma must be positive")
        if tau2 <= 0:
            raise ValueError("tau2 (mixing variance) must be positive")
        self.mu0 = float(mu0)
        self.sigma2 = float(sigma) ** 2
        self.tau2 = float(tau2)
        self._n = 0
        self._sum = 0.0
        self._running_max_lr = 1.0  # Lambda_0 == 1

    def _mixture_lr(self) -> float:
        n = self._n
        if n == 0:
            return 1.0
        xbar = self._sum / n
        denom = self.sigma2 + n * self.tau2
        coef = math.sqrt(self.sigma2 / denom)
        expo = (n**2 * self.tau2 * (xbar - self.mu0) ** 2) / (2.0 * self.sigma2 * denom)
        return coef * math.exp(expo)

    def update(self, x: float) -> float:
        """Feed one observation; return the current always-valid p-value."""
        self._n += 1
        self._sum += float(x)
        lr = self._mixture_lr()
        if lr > self._running_max_lr:
            self._running_max_lr = lr
        return self.always_valid_pvalue

    def update_many(self, xs: "Iterable[float]") -> float:
        for x in xs:
            self.update(x)
        return self.always_valid_pvalue

    @property
    def always_valid_pvalue(self) -> float:
        if self._running_max_lr <= 0:
            return 1.0
        return min(1.0, 1.0 / self._running_max_lr)

    @property
    def mixture_lr(self) -> float:
        return self._mixture_lr()

    @property
    def n(self) -> int:
        return self._n

    def decision(self, alpha: float = 0.05) -> str:
        """``reject_h0`` once the always-valid p-value crosses ``alpha``."""
        if not (0.0 < alpha < 1.0):
            raise ValueError("alpha must be in (0, 1)")
        return REJECT_H0 if self.always_valid_pvalue <= alpha else CONTINUE

    def state(self, alpha: float = 0.05) -> MixtureSPRTState:
        return MixtureSPRTState(
            n=self._n,
            mixture_lr=self._mixture_lr(),
            running_max_lr=self._running_max_lr,
            always_valid_pvalue=self.always_valid_pvalue,
            decision=self.decision(alpha),
        )

    def reset(self) -> None:
        self._n = 0
        self._sum = 0.0
        self._running_max_lr = 1.0
