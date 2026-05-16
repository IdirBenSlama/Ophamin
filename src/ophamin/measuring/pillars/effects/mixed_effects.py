"""Mixed-effects modelling (M pillar).

For longitudinal iterative experiments — repeated measurements from the same
subjects, or hierarchical multi-environment trials — the ordinary assumption of
independent observations is violated. A mixed-effects model combines *fixed
effects* (the treatments) with *random effects* (subject- or block-specific
variation).

The random-intercept model

    y_ij = X_ij . beta + u_i + e_ij ,   u_i ~ N(0, sigma_u^2),  e_ij ~ N(0, sigma_e^2)

is fitted by **statsmodels** ``MixedLM`` (REML by default) — the authoritative
Python linear-mixed-model implementation. ``RandomInterceptModel`` is a thin,
fixed-result-shape wrapper so the rest of the framework consumes a stable
interface; for random *slopes* or crossed effects, drive ``statsmodels.MixedLM``
directly with an explicit ``exog_re``.

``center_and_scale`` is a preprocessing helper — centring and scaling
continuous predictors materially improves the model's numerical conditioning.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from statsmodels.regression.mixed_linear_model import MixedLM


@dataclass
class MixedEffectsResult:
    """Fitted random-intercept model (extracted from a statsmodels MixedLM fit)."""

    fixed_effects: np.ndarray
    fixed_effects_se: np.ndarray
    sigma_u2: float          # random-intercept variance (statsmodels cov_re)
    sigma_e2: float          # residual variance (statsmodels scale)
    loglik: float
    n_obs: int
    n_groups: int
    converged: bool
    feature_names: list[str] = field(default_factory=list)

    @property
    def icc(self) -> float:
        """Intraclass correlation — share of variance between groups."""
        total = self.sigma_u2 + self.sigma_e2
        return self.sigma_u2 / total if total > 0 else 0.0

    def summary(self) -> str:
        names = self.feature_names or [f"x{i}" for i in range(len(self.fixed_effects))]
        lines = [
            f"RandomInterceptModel (statsmodels MixedLM)  n={self.n_obs} "
            f"groups={self.n_groups} converged={self.converged}",
            f"  sigma_u^2={self.sigma_u2:.4g}  sigma_e^2={self.sigma_e2:.4g}  "
            f"ICC={self.icc:.4f}  loglik={self.loglik:.4g}",
        ]
        for name, b, se in zip(names, self.fixed_effects, self.fixed_effects_se):
            z = b / se if se > 0 else float("nan")
            lines.append(f"  {name:<16} beta={b:+.4g}  se={se:.4g}  z={z:+.3f}")
        return "\n".join(lines)


def center_and_scale(
    X: np.ndarray, skip_constant: bool = True
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Centre and scale continuous predictors. Returns ``(X_scaled, mean, std)``.

    Columns with near-zero variance (an intercept column, a constant) are left
    untouched when ``skip_constant`` is set; ``mean`` is reported 0 and ``std``
    1 for them so the transform is invertible.
    """
    X = np.asarray(X, dtype=float)
    mean = X.mean(axis=0)
    std = X.std(axis=0, ddof=0)
    out = X.copy()
    keep_mean = np.zeros_like(mean)
    keep_std = np.ones_like(std)
    for j in range(X.shape[1]):
        if skip_constant and std[j] < 1e-12:
            continue
        keep_mean[j] = mean[j]
        keep_std[j] = std[j] if std[j] > 1e-12 else 1.0
        out[:, j] = (X[:, j] - keep_mean[j]) / keep_std[j]
    return out, keep_mean, keep_std


class RandomInterceptModel:
    """Random-intercept linear mixed model — a thin wrapper over statsmodels MixedLM."""

    def __init__(self, reml: bool = True) -> None:
        self.reml = bool(reml)

    def fit(
        self,
        y: Any,
        X: Any,
        groups: Any,
        fit_intercept: bool = True,
        feature_names: list[str] | None = None,
    ) -> MixedEffectsResult:
        """Fit the model.

        ``y`` outcome (n,). ``X`` fixed-effects design (n, p) — an intercept
        column is prepended when ``fit_intercept`` is set. ``groups`` is one
        label per observation identifying the random-effect grouping.
        """
        y = np.asarray(y, dtype=float).ravel()
        X = np.asarray(X, dtype=float)
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        if X.shape[0] != y.shape[0]:
            raise ValueError("X and y must have the same number of rows")
        groups = list(groups)
        if len(groups) != y.shape[0]:
            raise ValueError("groups must have one label per observation")

        names = list(feature_names) if feature_names else [f"x{i}" for i in range(X.shape[1])]
        if fit_intercept:
            X = np.column_stack([np.ones(X.shape[0]), X])
            names = ["intercept"] + names
        if len(names) != X.shape[1]:
            raise ValueError("feature_names length does not match the design matrix")

        n_groups = len(set(groups))
        if n_groups < 2:
            raise ValueError("random-intercept model needs at least 2 groups")

        # exog_re=None => statsmodels uses a random intercept (a column of ones)
        model = MixedLM(endog=y, exog=X, groups=groups)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # suppress statsmodels convergence chatter
            result = model.fit(reml=self.reml)

        cov_re = np.asarray(result.cov_re, dtype=float)
        return MixedEffectsResult(
            fixed_effects=np.asarray(result.fe_params, dtype=float),
            fixed_effects_se=np.asarray(result.bse_fe, dtype=float),
            sigma_u2=float(cov_re[0, 0]) if cov_re.size else 0.0,
            sigma_e2=float(result.scale),
            loglik=float(result.llf),
            n_obs=int(X.shape[0]),
            n_groups=n_groups,
            converged=bool(result.converged),
            feature_names=names,
        )
