"""Multi-Experiment Analysis (M pillar).

Hyperscale platforms run many overlapping experiments at once: the same units
are routed into multiple concurrent tests. MEA estimates effects in the
presence of arbitrary overlap:

    marginal_effect      effect of a variant against baseline, overlap ignored
    conditional_effect   effect of a variant *given* the variant assigned in
                         another concurrent experiment (a stratum)
    interaction_test     F-test for non-additivity between two experiments
    joint_estimate       one linear model over all experiments + pairwise
                         interactions

The MEA orchestration (marginal / conditional / stratification framing) is the
framework's own value-add — MEA is not itself a single library. Every actual
*estimate* is delegated:

    marginal / conditional contrasts  ->  scipy.stats.ttest_ind (Welch)
    interaction F-test, joint model   ->  statsmodels OLS + anova_lm
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats
from statsmodels.stats.anova import anova_lm


@dataclass
class EffectEstimate:
    """A treatment-vs-baseline contrast, optionally within a stratum."""

    experiment: str
    variant: Any
    baseline: Any
    effect: float
    se: float
    t_stat: float
    p_value: float
    n_treatment: int
    n_control: int
    ci_low: float
    ci_high: float
    stratum: dict[str, Any] | None = None

    def summary(self) -> str:
        where = f" | given {self.stratum}" if self.stratum else ""
        return (
            f"{self.experiment}={self.variant} vs {self.baseline}{where}: "
            f"effect={self.effect:+.4g} se={self.se:.4g} "
            f"p={self.p_value:.4g} 95%CI=({self.ci_low:+.4g}, {self.ci_high:+.4g})"
        )


@dataclass
class InteractionResult:
    """statsmodels F-test for interaction (non-additivity) between two experiments."""

    exp_a: str
    exp_b: str
    f_stat: float
    p_value: float
    df_num: int
    df_den: int

    def significant_at(self, alpha: float = 0.05) -> bool:
        return self.p_value < alpha

    def summary(self) -> str:
        return (
            f"interaction {self.exp_a} x {self.exp_b}: F={self.f_stat:.4g} "
            f"p={self.p_value:.4g} (df={self.df_num}, {self.df_den})"
        )


@dataclass
class Coefficient:
    name: str
    estimate: float
    se: float
    t_stat: float
    p_value: float


@dataclass
class JointEstimate:
    coefficients: list[Coefficient] = field(default_factory=list)
    r_squared: float = 0.0
    n_obs: int = 0

    def summary(self) -> str:
        lines = [f"joint estimate (statsmodels OLS)  n={self.n_obs}  R^2={self.r_squared:.4f}"]
        for c in self.coefficients:
            lines.append(
                f"  {c.name:<28} {c.estimate:+.4g}  se={c.se:.4g}  "
                f"t={c.t_stat:+.3f}  p={c.p_value:.4g}"
            )
        return "\n".join(lines)


class MultiExperimentAnalysis:
    """Joint analysis of overlapping experiments on a shared unit population."""

    def __init__(self, assignments: dict[str, Any], outcome: Any) -> None:
        if not assignments:
            raise ValueError("assignments must be non-empty")
        self.outcome = np.asarray(list(outcome), dtype=float)
        n = self.outcome.shape[0]
        if n < 4:
            raise ValueError("MEA needs at least 4 units")
        self.assignments: dict[str, np.ndarray] = {}
        for name, labels in assignments.items():
            arr = np.asarray(list(labels), dtype=object)
            if arr.shape[0] != n:
                raise ValueError(f"assignment '{name}' length does not match outcome")
            self.assignments[name] = arr
        self.n_units = n
        self.experiments = list(self.assignments)

    # -- inspection ---------------------------------------------------------

    def variants(self, experiment: str) -> list[Any]:
        self._require(experiment)
        return list(dict.fromkeys(self.assignments[experiment].tolist()))

    def _require(self, experiment: str) -> None:
        if experiment not in self.assignments:
            raise ValueError(f"unknown experiment '{experiment}'")

    def _baseline(self, experiment: str, baseline: Any) -> Any:
        variants = self.variants(experiment)
        if baseline is None:
            return variants[0]
        if baseline not in variants:
            raise ValueError(f"baseline {baseline!r} not a variant of '{experiment}'")
        return baseline

    # -- contrasts (scipy Welch two-sample) ---------------------------------

    def _two_sample(
        self,
        treat: np.ndarray,
        control: np.ndarray,
        experiment: str,
        variant: Any,
        baseline: Any,
        stratum: dict[str, Any] | None = None,
    ) -> EffectEstimate:
        if treat.size < 2 or control.size < 2:
            raise ValueError(
                f"need >=2 units in each arm for {experiment}={variant} "
                f"vs {baseline} (got {treat.size} / {control.size})"
            )
        effect = float(treat.mean() - control.mean())
        va = float(treat.var(ddof=1))
        vb = float(control.var(ddof=1))
        se = float(np.sqrt(va / treat.size + vb / control.size))
        test = stats.ttest_ind(treat, control, equal_var=False)
        if se > 0:
            df = (va / treat.size + vb / control.size) ** 2 / (
                (va / treat.size) ** 2 / (treat.size - 1)
                + (vb / control.size) ** 2 / (control.size - 1)
            )
            tcrit = float(stats.t.ppf(0.975, df))
        else:
            tcrit = 0.0
        return EffectEstimate(
            experiment=experiment,
            variant=variant,
            baseline=baseline,
            effect=effect,
            se=se,
            t_stat=float(test.statistic),
            p_value=float(test.pvalue),
            n_treatment=int(treat.size),
            n_control=int(control.size),
            ci_low=effect - tcrit * se,
            ci_high=effect + tcrit * se,
            stratum=stratum,
        )

    def marginal_effect(
        self, experiment: str, baseline: Any = None
    ) -> dict[Any, EffectEstimate]:
        """Effect of each variant vs baseline, ignoring overlap with other tests."""
        self._require(experiment)
        base = self._baseline(experiment, baseline)
        labels = self.assignments[experiment]
        control = self.outcome[labels == base]
        out: dict[Any, EffectEstimate] = {}
        for v in self.variants(experiment):
            if v == base:
                continue
            out[v] = self._two_sample(
                self.outcome[labels == v], control, experiment, v, base
            )
        return out

    def conditional_effect(
        self,
        experiment: str,
        given: dict[str, Any],
        baseline: Any = None,
    ) -> dict[Any, EffectEstimate]:
        """Effect of each variant vs baseline *within a stratum* of other tests."""
        self._require(experiment)
        for exp in given:
            self._require(exp)
        mask = np.ones(self.n_units, dtype=bool)
        for exp, val in given.items():
            mask &= self.assignments[exp] == val
        if not mask.any():
            raise ValueError(f"stratum {given} contains no units")
        labels = self.assignments[experiment][mask]
        outcome = self.outcome[mask]
        base = self._baseline(experiment, baseline)
        control = outcome[labels == base]
        out: dict[Any, EffectEstimate] = {}
        for v in self.variants(experiment):
            if v == base:
                continue
            out[v] = self._two_sample(
                outcome[labels == v], control, experiment, v, base, stratum=dict(given)
            )
        return out

    # -- linear models (statsmodels) ---------------------------------------

    def interaction_test(self, exp_a: str, exp_b: str) -> InteractionResult:
        """statsmodels F-test for the ``A:B`` interaction (Type-II ANOVA)."""
        self._require(exp_a)
        self._require(exp_b)
        if len(self.variants(exp_a)) < 2 or len(self.variants(exp_b)) < 2:
            raise ValueError("interaction test needs >=2 variants in each experiment")
        df = pd.DataFrame(
            {
                "outcome": self.outcome,
                "A": self.assignments[exp_a].astype(str),
                "B": self.assignments[exp_b].astype(str),
            }
        )
        model = smf.ols("outcome ~ C(A) * C(B)", data=df).fit()
        if model.df_resid <= 0:
            raise ValueError("design is saturated — no residual degrees of freedom")
        aov = anova_lm(model, typ=2)
        if "C(A):C(B)" not in aov.index:
            raise ValueError("interaction term not estimable for this design")
        row = aov.loc["C(A):C(B)"]
        return InteractionResult(
            exp_a=exp_a,
            exp_b=exp_b,
            f_stat=float(row["F"]),
            p_value=float(row["PR(>F)"]),
            df_num=int(row["df"]),
            df_den=int(aov.loc["Residual", "df"]),
        )

    def joint_estimate(self, include_interactions: bool = True) -> JointEstimate:
        """One statsmodels OLS over all experiments + pairwise interactions."""
        df = pd.DataFrame({"outcome": self.outcome})
        cols: list[str] = []
        for i, exp in enumerate(self.experiments):
            col = f"E{i}"
            df[col] = self.assignments[exp].astype(str)
            cols.append(col)
        terms = [f"C({c})" for c in cols]
        if include_interactions and len(cols) >= 2:
            for ai in range(len(cols)):
                for bi in range(ai + 1, len(cols)):
                    terms.append(f"C({cols[ai]}):C({cols[bi]})")
        formula = "outcome ~ " + " + ".join(terms)
        model = smf.ols(formula, data=df).fit()
        if model.df_resid <= 0:
            raise ValueError("design is saturated — no residual degrees of freedom")
        coeffs = [
            Coefficient(
                name=str(name),
                estimate=float(model.params[name]),
                se=float(model.bse[name]),
                t_stat=float(model.tvalues[name]),
                p_value=float(model.pvalues[name]),
            )
            for name in model.params.index
        ]
        return JointEstimate(
            coefficients=coeffs,
            r_squared=float(model.rsquared),
            n_obs=int(model.nobs),
        )
