"""scipy ↔ statsmodels ↔ pingouin Welch's t-test cross-check (RFC 0002 Phase E1.5).

Welch's two-sample t-test (unequal-variance) is the load-bearing
means-difference primitive across the Ophamin pillar dep tree. Three
*genuinely independent* implementations are reachable from
``[analytic]``:

* :func:`scipy.stats.ttest_ind(x, y, equal_var=False)` — scipy's
  canonical entry point.
* :func:`statsmodels.stats.weightstats.ttest_ind(x, y, usevar='unequal')`
  — statsmodels' independent implementation. Does NOT delegate to
  scipy; uses its own variance-pooling code path.
* :func:`pingouin.ttest(x, y, paired=False, correction=True)` — the
  effect-size-rich wrapper; computes Welch correction itself.

All three compute the same Welch t-statistic and two-sided p-value
from the same data. They MUST agree to floating-point tolerance.
Three-way agreement with one genuinely-independent implementation
(statsmodels) is a tighter cross-validation than Spearman's two-way
(where pingouin delegates to scipy).

VALIDATED iff every pairwise comparison agrees across N samples on
both the t-statistic and the p-value. REFUTED if any backend pair
disagrees by more than the tolerance on either statistic.

Reference: RFC 0002 §3.1 E1 ("cross-framework validation studies").
This is the fifth shipped cross-framework check.
"""

from __future__ import annotations

from typing import Any

from ophamin import __version__
from ophamin._stability import Stable
from ophamin.comparing.provenance import ProvenanceGraph
from ophamin.comparing.provenance.lineage import (
    _ophamin_project_root,
    capture_git_commit,
)
from ophamin.measuring.proof import (
    Claim,
    DatasetRef,
    EmpiricalProofRecord,
    PillarEvidence,
    PreRegistration,
    Reproduction,
    Threshold,
    Verdict,
    content_hash,
)
from ophamin.measuring.scenarios.base import (
    DEFAULT_SIGN_KEY,
    Scenario,
    ScenarioScore,
    Tier,
)
from ophamin.seeing.corpus import CorpusRecord
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest


@Stable(since="0.14.0", notes="RFC-0002 Phase E1.5 — three-way Welch t-test cross-framework validation.")
class WelchTTestCrosscheckScenario(Scenario):
    """scipy vs statsmodels vs pingouin Welch's t-test cross-check.

    Generates N ``(x, y)`` independent-sample pairs from a fixed seed,
    sweeping the effect size and group-size combinations. For each
    pair, computes the Welch t-statistic AND the two-sided p-value
    under all three backends. Asserts every pairwise comparison agrees
    within ``tolerance`` on BOTH statistics.

    Args:
        n_pairs: number of independent ``(x, y)`` sample pairs.
            Default 30.
        sample_size: observations per group. Default 50.
        seed: deterministic seed for the pair generator.
        tolerance: maximum allowed absolute difference between any
            two backends. Default 1e-9. Empirically all three
            backends agree at ~4e-16 (a few × machine epsilon) for
            Welch's t-test; ≤ 1e-9 is the loud-failure threshold for
            a real upstream defect.
    """

    name = "welch-t-crosscheck"
    tier = Tier.MEASUREMENT_MACHINERY
    family = "cross_framework"
    goal = (
        "Verify the Welch's t-test implementations Ophamin depends on "
        "(scipy / statsmodels / pingouin) all produce the same "
        "t-statistic and p-value to floating-point tolerance across "
        "30 independent-sample pairs."
    )
    explanation = (
        "Welch's t-test is the unequal-variance two-sample means "
        "comparison every Ophamin pillar that makes a between-group "
        "claim ultimately calls. scipy.stats.ttest_ind, "
        "statsmodels.stats.weightstats.ttest_ind, and pingouin.ttest "
        "implement the formula via independent code paths "
        "(statsmodels in particular does NOT delegate to scipy). "
        "Three-way agreement at machine epsilon is the strongest "
        "empirical signal that none has regressed."
    )
    method = "cross_framework_oracle"
    falsification_consequence = (
        "scipy / statsmodels / pingouin disagree on Welch t or p by "
        "more than the documented float-precision tolerance — at "
        "least one library has a defect in variance pooling, "
        "Satterthwaite-degrees-of-freedom, or the t-CDF p-value "
        "calculation."
    )
    corpus_name = "synthetic-welch-t-pairs"
    target = "scipy+statsmodels+pingouin-cross-framework"

    def __init__(
        self,
        *,
        n_pairs: int = 30,
        sample_size: int = 50,
        seed: int = 20260518,
        tolerance: float = 1e-9,
    ) -> None:
        if n_pairs < 1:
            raise ValueError(f"n_pairs must be ≥ 1, got {n_pairs}")
        if sample_size < 3:
            raise ValueError(f"sample_size must be ≥ 3, got {sample_size}")
        if tolerance <= 0.0:
            raise ValueError(f"tolerance must be > 0, got {tolerance}")
        self.n_pairs = int(n_pairs)
        self.sample_size = int(sample_size)
        self.seed = int(seed)
        self.tolerance = float(tolerance)
        self.n_cycles = 0

    def score(
        self,
        cycle_results: list[CycleResult],
        records: list[CorpusRecord],
    ) -> ScenarioScore:
        raise NotImplementedError(
            "WelchTTestCrosscheckScenario uses a custom run(); "
            "score() is unreachable."
        )

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                f"Across {self.n_pairs} synthetic two-sample pairs of "
                f"size {self.sample_size} per group with varying effect "
                f"sizes and variance ratios (seed={self.seed}), "
                f"``scipy.stats.ttest_ind(equal_var=False)``, "
                f"``statsmodels.stats.weightstats.ttest_ind(usevar='unequal')``, "
                f"and ``pingouin.ttest(correction=True)`` produce Welch "
                f"t-statistics AND two-sided p-values that agree to ≤ "
                f"{self.tolerance:g} across all pairwise comparisons. "
                f"(RFC 0002 Phase E1: cross-framework validation; "
                f"three-way variant with genuinely-independent statsmodels.)"
            ),
            operationalization=(
                "Generate N (x, y) pairs where x ~ Normal(0, σ_x²) and "
                "y ~ Normal(δ, σ_y²) for a sweep of δ across "
                "[-1.0, 1.0] and variance-ratio σ_y/σ_x across "
                "[0.5, 2.0]. Compute Welch's t and two-sided p under "
                "each backend. Compute max_abs_diff = max over (pair, "
                "statistic ∈ {t, p}, backend-pair) of |stat_a - stat_b|. "
                "VALIDATED iff max_abs_diff ≤ tolerance."
            ),
            threshold=Threshold(
                metric="max_absolute_welch_difference",
                comparator="<=",
                value=self.tolerance,
                units="t_or_p",
            ),
            h0=(
                "At least one backend pair disagrees on the Welch "
                "t-statistic OR the two-sided p-value by more than "
                "the floating-point tolerance."
            ),
            h1=(
                "All three backends compute identical Welch t AND p "
                "to floating-point tolerance across every pair."
            ),
        )

    def run(
        self,
        substrate: SubstrateUnderTest | None = None,  # noqa: ARG002
        *,
        data_root: Any = None,
        sign_key: bytes = DEFAULT_SIGN_KEY,
    ) -> EmpiricalProofRecord:
        try:
            import numpy as np
            import pingouin
            import scipy
            import statsmodels
            from scipy.stats import ttest_ind as scipy_ttest_ind
            from statsmodels.stats.weightstats import ttest_ind as sm_ttest_ind
        except ImportError as exc:
            raise RuntimeError(
                "WelchTTestCrosscheckScenario requires scipy + statsmodels "
                "+ pingouin. Install via `pip install 'ophamin[analytic]'`. "
                f"({exc})"
            ) from exc

        rng = np.random.default_rng(self.seed)
        # Sweep effect-size δ across [-1, 1] and variance-ratio across
        # [0.5, 2.0] in a Latin-hypercube-style raster, so each pair
        # exercises a different (δ, σ_y) regime.
        deltas = np.linspace(-1.0, 1.0, self.n_pairs)
        sigma_ratios = np.linspace(0.5, 2.0, self.n_pairs)
        # Shuffle σ ratios deterministically so they're decoupled from δ.
        rng_shuffle = np.random.default_rng(self.seed + 1)
        rng_shuffle.shuffle(sigma_ratios)

        max_abs_diff = 0.0
        worst_pair_label = ""
        worst_statistic = ""
        per_pair: list[dict[str, Any]] = []
        for i in range(self.n_pairs):
            delta = float(deltas[i])
            sigma_ratio = float(sigma_ratios[i])
            x = rng.standard_normal(self.sample_size)
            y = delta + sigma_ratio * rng.standard_normal(self.sample_size)

            # Backend A: scipy
            sa = scipy_ttest_ind(x, y, equal_var=False)
            t_scipy = float(sa.statistic)
            p_scipy = float(sa.pvalue)

            # Backend B: statsmodels (genuinely independent path)
            t_sm, p_sm, _ = sm_ttest_ind(x, y, usevar="unequal")
            t_sm = float(t_sm)
            p_sm = float(p_sm)

            # Backend C: pingouin (correction=True → Welch)
            pg = pingouin.ttest(
                x, y, paired=False, alternative="two-sided", correction=True
            )
            t_pg = float(pg["T"].iloc[0])
            p_pg = float(pg["p_val"].iloc[0])

            # Three pairwise distances on each statistic
            dt_sn = abs(t_scipy - t_sm)
            dt_sp = abs(t_scipy - t_pg)
            dt_np = abs(t_sm - t_pg)
            dp_sn = abs(p_scipy - p_sm)
            dp_sp = abs(p_scipy - p_pg)
            dp_np = abs(p_sm - p_pg)

            local_max = max(dt_sn, dt_sp, dt_np, dp_sn, dp_sp, dp_np)
            if local_max > max_abs_diff:
                max_abs_diff = local_max
                # Identify which (statistic, pair) is the worst.
                labels = [
                    ("t", "scipy_vs_statsmodels", dt_sn),
                    ("t", "scipy_vs_pingouin", dt_sp),
                    ("t", "statsmodels_vs_pingouin", dt_np),
                    ("p", "scipy_vs_statsmodels", dp_sn),
                    ("p", "scipy_vs_pingouin", dp_sp),
                    ("p", "statsmodels_vs_pingouin", dp_np),
                ]
                worst = max(labels, key=lambda lp: lp[2])
                worst_statistic, worst_pair_label, _ = worst

            if i < 5 or local_max > self.tolerance:
                per_pair.append({
                    "i": i,
                    "delta": delta,
                    "sigma_ratio": sigma_ratio,
                    "t_scipy": t_scipy,
                    "t_statsmodels": t_sm,
                    "t_pingouin": t_pg,
                    "p_scipy": p_scipy,
                    "p_statsmodels": p_sm,
                    "p_pingouin": p_pg,
                    "max_pair_diff": local_max,
                })

        agrees = max_abs_diff <= self.tolerance

        config = {
            "scenario": self.name,
            "n_pairs": self.n_pairs,
            "sample_size": self.sample_size,
            "seed": self.seed,
            "tolerance": self.tolerance,
        }
        dataset = DatasetRef(
            name=self.corpus_name,
            content_hash=content_hash(config),
            n_records=self.n_pairs,
            source=f"numpy.random.default_rng(seed={self.seed})",
            kind="synthetic-welch-t-pairs",
        )
        prereg = PreRegistration(
            config_hash=content_hash(config),
            data_hash=dataset.content_hash,
            analysis_plan=self.analysis_plan(),
        )

        claim = self.build_claim()
        verdict = Verdict.decide(
            observed=max_abs_diff,
            threshold=claim.threshold,
            reasoning=(
                f"{self.n_pairs} pairs × 3 backends × 2 statistics; "
                f"max pairwise |Δ| = {max_abs_diff:.3e} on "
                f"({worst_statistic}, {worst_pair_label or 'none'}) "
                f"({'≤' if agrees else '>'} {self.tolerance:.0e} tol)"
            ),
        )

        evidence = [
            PillarEvidence(
                pillar="welch_t_scipy_vs_statsmodels_vs_pingouin",
                statistic_name="max_absolute_welch_difference",
                statistic_value=max_abs_diff,
                library="scipy",
                library_version=getattr(scipy, "__version__", "unknown"),
                effect_size=None,
                ci_low=None,
                ci_high=None,
                p_value=None,
                cross_check="passed" if agrees else "failed",
                detail={
                    "cross_check_note": (
                        f"scipy {getattr(scipy, '__version__', 'unknown')} "
                        f"vs statsmodels "
                        f"{getattr(statsmodels, '__version__', 'unknown')} "
                        f"vs pingouin "
                        f"{getattr(pingouin, '__version__', 'unknown')} "
                        f"— three-way Welch t-test agreement on both "
                        f"the t-statistic and the two-sided p-value"
                    ),
                    "scipy_version": getattr(scipy, "__version__", "unknown"),
                    "statsmodels_version": getattr(
                        statsmodels, "__version__", "unknown"
                    ),
                    "pingouin_version": getattr(
                        pingouin, "__version__", "unknown"
                    ),
                    "n_pairs": self.n_pairs,
                    "sample_size": self.sample_size,
                    "seed": self.seed,
                    "tolerance": self.tolerance,
                    "max_abs_diff": max_abs_diff,
                    "worst_statistic": worst_statistic,
                    "worst_pair": worst_pair_label,
                    "sample_pairs": per_pair,
                },
            ),
        ]

        prov = ProvenanceGraph()
        agent_ophamin = prov.agent(
            "ophamin", role="experimentation_framework", version=__version__
        )
        agent_scipy = prov.agent(
            "scipy", role="welch_t_backend_a",
            version=getattr(scipy, "__version__", "unknown"),
        )
        agent_sm = prov.agent(
            "statsmodels", role="welch_t_backend_b_independent",
            version=getattr(statsmodels, "__version__", "unknown"),
        )
        agent_pg = prov.agent(
            "pingouin", role="welch_t_backend_c_oracle",
            version=getattr(pingouin, "__version__", "unknown"),
        )
        data_entity = prov.entity(
            f"corpus:{dataset.name}",
            content_hash=dataset.content_hash,
            n_records=dataset.n_records,
            kind=dataset.kind,
        )
        activity = prov.activity(
            f"scenario:{self.name}",
            target=self.target,
            n_pairs=self.n_pairs,
        )
        result_entity = prov.entity(f"proof:{self.name}")
        prov.used(activity, data_entity)
        prov.was_associated_with(activity, agent_ophamin)
        prov.was_associated_with(activity, agent_scipy)
        prov.was_associated_with(activity, agent_sm)
        prov.was_associated_with(activity, agent_pg)
        prov.was_generated_by(result_entity, activity)
        prov.was_derived_from(result_entity, data_entity)

        proof = EmpiricalProofRecord(
            claim=claim,
            preregistration=prereg,
            datasets=[dataset],
            substrate_name="scipy+statsmodels+pingouin-cross-framework",
            substrate_git_commit=capture_git_commit(_ophamin_project_root()),
            evidence=evidence,
            verdict=verdict,
            reproduction=Reproduction(
                command=(
                    f"PYTHONPATH=src .venv/bin/python -m ophamin.cli scenario "
                    f"{self.name} --n-pairs {self.n_pairs} --seed {self.seed}"
                )
            ),
            provenance=prov.to_prov_json(),
            ophamin_version=__version__,
            ophamin_git_commit=capture_git_commit(_ophamin_project_root()),
        )
        proof.sign(sign_key)
        return proof

    def analysis_plan(self) -> str:
        return (
            f"Generate {self.n_pairs} two-sample pairs of size "
            f"{self.sample_size} per group, sweeping effect-size δ "
            f"across [-1, 1] and variance-ratio σ_y/σ_x across "
            f"[0.5, 2.0] (deterministically shuffled), seed={self.seed}. "
            f"Compute Welch's t AND two-sided p under "
            f"scipy.stats.ttest_ind(equal_var=False), "
            f"statsmodels.stats.weightstats.ttest_ind(usevar='unequal'), "
            f"and pingouin.ttest(correction=True). For each pair, "
            f"compute all six pairwise distances (3 backend pairs × 2 "
            f"statistics). Track the maximum. VALIDATED iff "
            f"max_abs_diff ≤ {self.tolerance:g}."
        )


__all__ = ["WelchTTestCrosscheckScenario"]
