"""Cumulative Meta-Analysis (I pillar).

Verifying isolated iterations has limited value. CMA recalculates the pooled
effect size and its uncertainty every time a new iteration completes; as
iterations accumulate the confidence interval narrows, revealing the point at
which an effect reaches stable significance.

Each step's pooling is delegated to **statsmodels**
``stats.meta_analysis.combine_effects`` — fixed-effect and DerSimonian-Laird
random-effects pooling with the heterogeneity statistics Q / I^2 / tau^2. The
framework's own value-add is the *cumulative* layer:

  * recompute after every iteration and keep the full trajectory;
  * find the iteration of *stable* significance;
  * the two-stage tau^2 freeze — once enough iterations have accumulated,
    tau^2 is held fixed and later iterations are pooled by inverse-variance
    weighting with that fixed value.

statsmodels' raw DL tau^2 / I^2 can go slightly negative when studies are more
homogeneous than chance; per standard meta-analysis practice the surfaced
values are clamped at 0.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Iterable

import numpy as np
from scipy import stats
from statsmodels.stats.meta_analysis import combine_effects


@dataclass
class CMAResult:
    """Cumulative pooled estimate after k iterations."""

    k: int
    model: str  # "fixed" or "random"
    estimate: float
    variance: float
    ci_low: float
    ci_high: float
    tau2: float
    q: float
    i_squared: float  # heterogeneity percentage [0, 100]

    @property
    def ci_width(self) -> float:
        return self.ci_high - self.ci_low

    @property
    def significant(self) -> bool:
        """True when the CI excludes zero."""
        return self.ci_low > 0.0 or self.ci_high < 0.0

    def summary(self) -> str:
        return (
            f"k={self.k} [{self.model}] estimate={self.estimate:.4g} "
            f"95%CI=({self.ci_low:.4g}, {self.ci_high:.4g}) "
            f"tau2={self.tau2:.4g} I^2={self.i_squared:.1f}% "
            f"{'SIGNIFICANT' if self.significant else 'not significant'}"
        )


class CumulativeMetaAnalysis:
    """Sequentially pools (effect, variance) pairs as iterations complete."""

    def __init__(
        self,
        random_effects: bool = True,
        tau2_fixed_after: int | None = None,
        confidence: float = 0.95,
    ) -> None:
        if not (0.0 < confidence < 1.0):
            raise ValueError("confidence must be in (0, 1)")
        if tau2_fixed_after is not None and tau2_fixed_after < 1:
            raise ValueError("tau2_fixed_after must be >= 1 when set")
        self.random_effects = bool(random_effects)
        self.tau2_fixed_after = tau2_fixed_after
        self.confidence = float(confidence)
        self._z = float(stats.norm.ppf(0.5 + confidence / 2.0))
        self._effects: list[float] = []
        self._variances: list[float] = []
        self._trajectory: list[CMAResult] = []
        self._frozen_tau2: float | None = None

    def add(self, effect: float, variance: float) -> CMAResult:
        """Add one iteration's effect estimate and recompute the pooled result."""
        if variance <= 0:
            raise ValueError("variance must be positive")
        self._effects.append(float(effect))
        self._variances.append(float(variance))
        result = self._compute()
        self._trajectory.append(result)
        return result

    def add_many(self, effects: "Iterable[float]", variances: "Iterable[float]") -> CMAResult:
        effects = list(effects)
        variances = list(variances)
        if len(effects) != len(variances):
            raise ValueError("effects and variances must be the same length")
        for e, v in zip(effects, variances):
            self.add(e, v)
        return self.result()

    def _compute(self) -> CMAResult:
        y = np.asarray(self._effects, dtype=float)
        v = np.asarray(self._variances, dtype=float)
        k = len(y)
        model = "random" if self.random_effects else "fixed"

        if k == 1:
            est, var = float(y[0]), float(v[0])
            se = var**0.5
            return CMAResult(
                k=1,
                model=model,
                estimate=est,
                variance=var,
                ci_low=est - self._z * se,
                ci_high=est + self._z * se,
                tau2=0.0,
                q=0.0,
                i_squared=0.0,
            )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            res = combine_effects(y, v, method_re="dl")
        q = float(res.q)
        i_squared = float(max(0.0, res.i2) * 100.0)
        tau2_dl = float(max(0.0, res.tau2))

        if not self.random_effects:
            estimate = float(res.mean_effect_fe)
            se = float(res.sd_eff_w_fe)
            tau2 = 0.0
        elif self.tau2_fixed_after is not None and k >= self.tau2_fixed_after:
            # two-stage: freeze tau^2 and pool by inverse-variance weighting
            if self._frozen_tau2 is None:
                self._frozen_tau2 = tau2_dl
            tau2 = self._frozen_tau2
            w = 1.0 / (v + tau2)
            estimate = float((w * y).sum() / w.sum())
            se = float(np.sqrt(1.0 / w.sum()))
        else:
            tau2 = tau2_dl
            estimate = float(res.mean_effect_re)
            se = float(res.sd_eff_w_re)

        return CMAResult(
            k=k,
            model=model,
            estimate=estimate,
            variance=se**2,
            ci_low=estimate - self._z * se,
            ci_high=estimate + self._z * se,
            tau2=tau2,
            q=q,
            i_squared=i_squared,
        )

    def result(self) -> CMAResult:
        """The current cumulative pooled estimate."""
        if not self._trajectory:
            raise RuntimeError("no iterations added yet")
        return self._trajectory[-1]

    def trajectory(self) -> list[CMAResult]:
        """The full cumulative trace — one CMAResult per iteration added."""
        return list(self._trajectory)

    def first_significant_k(self) -> int | None:
        """The iteration count at which the CI first (and lastingly) excludes zero.

        Returns the smallest k such that every result from k onward is
        significant — the point of *stable* significance. ``None`` if the trace
        never stabilises.
        """
        traj = self._trajectory
        for i in range(len(traj)):
            if all(r.significant for r in traj[i:]):
                return traj[i].k
        return None

    def plot(self, path: str) -> str:
        """Render the cumulative forest plot (narrowing CIs) to ``path``.

        Requires the ``viz`` extra (matplotlib). Raises a clear error if it is
        not installed — the framework never silently skips a requested output.
        """
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise RuntimeError(
                "CumulativeMetaAnalysis.plot requires matplotlib — "
                "install the 'viz' extra: pip install 'ophamin[viz]'"
            ) from exc

        if not self._trajectory:
            raise RuntimeError("no iterations to plot")

        ks = [r.k for r in self._trajectory]
        est = [r.estimate for r in self._trajectory]
        lo = [r.ci_low for r in self._trajectory]
        hi = [r.ci_high for r in self._trajectory]

        fig, ax = plt.subplots(figsize=(8, 5))
        ax.errorbar(
            est,
            ks,
            xerr=[np.array(est) - np.array(lo), np.array(hi) - np.array(est)],
            fmt="o",
            capsize=3,
        )
        ax.axvline(0.0, color="grey", linestyle="--", linewidth=1)
        ax.set_xlabel("pooled effect size")
        ax.set_ylabel("iterations accumulated (k)")
        ax.set_title("Cumulative meta-analysis — narrowing confidence interval")
        ax.invert_yaxis()
        fig.tight_layout()
        fig.savefig(path, dpi=120)
        plt.close(fig)
        return path
