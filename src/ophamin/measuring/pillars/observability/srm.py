"""Sample Ratio Mismatch detection (O pillar).

SRM occurs when the empirically observed allocation of units across variants
deviates from the configured expectation (e.g. an observed 40/60 split in a
test designed for 50/50). It is not noise — it indicates a survivorship bias,
caching error, or telemetry failure that breaks the assumptions of every
downstream statistical test, rendering the resulting p-values untrustworthy.

Detection is a chi-squared goodness-of-fit test against an aggressive
threshold. On a positive detection the experiment should be halted and the
data segmented by covariate to locate the root cause before proceeding.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import stats


@dataclass
class SRMResult:
    """Outcome of one SRM check."""

    chi2: float
    pvalue: float
    dof: int
    is_mismatch: bool
    alpha: float
    observed: dict[str, int] = field(default_factory=dict)
    expected: dict[str, float] = field(default_factory=dict)

    def summary(self) -> str:
        verdict = "MISMATCH" if self.is_mismatch else "ok"
        return (
            f"SRM {verdict}: chi2={self.chi2:.4g} p={self.pvalue:.4g} "
            f"(dof={self.dof}, alpha={self.alpha:g}) "
            f"observed={self.observed} expected="
            f"{{{', '.join(f'{k}: {v:.1f}' for k, v in self.expected.items())}}}"
        )


class SRMDetector:
    """Chi-squared goodness-of-fit detector for sample ratio mismatch.

    ``expected_ratios`` need not sum to 1 — they are normalised. ``alpha`` is
    intentionally aggressive (0.001 by default): an SRM is a validity failure,
    so a low false-negative rate matters more than a low false-positive rate.
    """

    def __init__(self, expected_ratios: dict[str, float], alpha: float = 0.001) -> None:
        if not expected_ratios:
            raise ValueError("expected_ratios must be non-empty")
        if any(r < 0 for r in expected_ratios.values()):
            raise ValueError("expected_ratios must be non-negative")
        total = float(sum(expected_ratios.values()))
        if total <= 0:
            raise ValueError("expected_ratios must sum to a positive value")
        if not (0.0 < alpha < 1.0):
            raise ValueError("alpha must be in (0, 1)")
        self.expected_ratios = {k: v / total for k, v in expected_ratios.items()}
        self.alpha = float(alpha)

    def check(self, observed_counts: dict[str, int]) -> SRMResult:
        """Run the chi-squared goodness-of-fit test on observed allocations."""
        keys = list(self.expected_ratios)
        missing = set(keys) - set(observed_counts)
        if missing:
            raise ValueError(f"observed_counts missing variants: {sorted(missing)}")
        extra = set(observed_counts) - set(keys)
        if extra:
            raise ValueError(f"observed_counts has unexpected variants: {sorted(extra)}")

        obs = np.array([observed_counts[k] for k in keys], dtype=float)
        if np.any(obs < 0):
            raise ValueError("observed counts must be non-negative")
        n = float(obs.sum())
        if n <= 0:
            raise ValueError("observed counts sum to zero — nothing to test")

        exp = np.array([self.expected_ratios[k] * n for k in keys], dtype=float)
        # chi-squared goodness of fit via scipy; dof = k - 1 (ddof default 0)
        dof = len(keys) - 1
        if dof > 0:
            gof = stats.chisquare(f_obs=obs, f_exp=exp)
            chi2 = float(gof.statistic)
            pvalue = float(gof.pvalue)
        else:
            chi2, pvalue = 0.0, 1.0

        return SRMResult(
            chi2=chi2,
            pvalue=pvalue,
            dof=dof,
            is_mismatch=pvalue < self.alpha,
            alpha=self.alpha,
            observed={k: int(observed_counts[k]) for k in keys},
            expected={k: float(self.expected_ratios[k] * n) for k in keys},
        )

    def segmented_check(
        self, observed_by_segment: dict[str, dict[str, int]]
    ) -> dict[str, SRMResult]:
        """Run the SRM check independently per covariate segment.

        This is the root-cause step: a global SRM is localised by checking
        whether the mismatch is isolated to specific browsers, regions, bot
        traffic, etc., or is a deeper failure of the randomisation unit.
        """
        return {seg: self.check(counts) for seg, counts in observed_by_segment.items()}

    def diagnose(
        self, observed_by_segment: dict[str, dict[str, int]]
    ) -> list[tuple[str, SRMResult]]:
        """Return segments sorted worst-first (lowest p-value), mismatches only."""
        results = self.segmented_check(observed_by_segment)
        offenders = [(seg, r) for seg, r in results.items() if r.is_mismatch]
        offenders.sort(key=lambda kr: kr[1].pvalue)
        return offenders
