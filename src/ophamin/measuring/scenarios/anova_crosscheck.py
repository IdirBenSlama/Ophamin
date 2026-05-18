"""scipy ↔ statsmodels ↔ pingouin one-way ANOVA cross-check (RFC 0002 Phase E1.6).

One-way ANOVA (F-test for equality of means across k ≥ 3 groups) is
the load-bearing multi-group means-difference primitive across the
Ophamin pillar dep tree (it underpins any "between-group" claim the
framework makes when more than two groups are present). Three
genuinely independent implementations are reachable from
``[analytic]``:

* :func:`scipy.stats.f_oneway(*groups)` — scipy's canonical entry.
* :func:`statsmodels.stats.anova.anova_lm` driven by an OLS fit on a
  long-format DataFrame — the regression-anchored ANOVA path that
  most statsmodels users reach.
* :func:`pingouin.anova` — the effect-size-rich wrapper.

All three compute the same F-statistic and two-sided p-value from
the same data. They MUST agree to floating-point tolerance.
Three-way agreement with two genuinely-independent
implementations (statsmodels via OLS, pingouin via its own path) is
a tighter cross-validation than Spearman's two-way.

VALIDATED iff every pairwise comparison agrees across N samples on
both the F statistic and the p value. REFUTED if any backend pair
disagrees by more than the tolerance on either.

Reference: RFC 0002 §3.1 E1 ("cross-framework validation studies").
Sixth shipped cross-framework check, lifting the count to 6 across
five distinct statistical-primitive families (Bayesian inference,
proportion CI, rank correlation, product-moment correlation,
two-sample means difference, multi-group means difference).
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


@Stable(since="0.15.0", notes="RFC-0002 Phase E1.6 — three-way one-way ANOVA cross-framework validation.")
class OneWayAnovaCrosscheckScenario(Scenario):
    """scipy vs statsmodels vs pingouin one-way ANOVA cross-check.

    Generates N synthetic three-group datasets from a fixed seed,
    sweeping the per-group means and shared σ across regimes that
    exercise both null and alternative cases. For each dataset,
    computes the F statistic AND the two-sided p value under all
    three backends. Asserts every pairwise comparison agrees within
    ``tolerance`` on BOTH statistics.

    Args:
        n_datasets: number of synthetic datasets. Default 30.
        sample_size: observations per group. Default 30.
        seed: deterministic seed for the dataset generator.
        tolerance: maximum allowed absolute pairwise difference.
            Default 1e-9. Empirically all three backends agree at
            ~7e-15 on F (a few × machine epsilon) and at p-value
            agreement of ~4e-19; ≤ 1e-9 is the loud-failure
            threshold for a real upstream defect.
    """

    name = "anova-crosscheck"
    tier = Tier.MEASUREMENT_MACHINERY
    family = "cross_framework"
    goal = (
        "Verify the one-way ANOVA implementations Ophamin depends on "
        "(scipy / statsmodels / pingouin) all produce the same "
        "F-statistic and p-value to floating-point tolerance across "
        "30 synthetic three-group datasets."
    )
    explanation = (
        "One-way ANOVA generalises the two-sample t-test to k ≥ 3 "
        "groups. scipy.stats.f_oneway, statsmodels' OLS + anova_lm, "
        "and pingouin.anova reach the same F-statistic via "
        "independent code paths. Three-way agreement at machine "
        "epsilon is the strongest empirical signal that none has "
        "regressed."
    )
    method = "cross_framework_oracle"
    falsification_consequence = (
        "scipy / statsmodels / pingouin disagree on the ANOVA "
        "F-statistic or p-value by more than the documented "
        "float-precision tolerance — at least one library has a "
        "defect in sum-of-squares decomposition, degrees-of-freedom "
        "accounting, or the F-CDF p-value computation."
    )
    corpus_name = "synthetic-anova-three-group"
    target = "scipy+statsmodels+pingouin-cross-framework"

    def __init__(
        self,
        *,
        n_datasets: int = 30,
        sample_size: int = 30,
        seed: int = 20260518,
        tolerance: float = 1e-9,
    ) -> None:
        if n_datasets < 1:
            raise ValueError(f"n_datasets must be ≥ 1, got {n_datasets}")
        if sample_size < 3:
            raise ValueError(f"sample_size must be ≥ 3, got {sample_size}")
        if tolerance <= 0.0:
            raise ValueError(f"tolerance must be > 0, got {tolerance}")
        self.n_datasets = int(n_datasets)
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
            "OneWayAnovaCrosscheckScenario uses a custom run(); "
            "score() is unreachable."
        )

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                f"Across {self.n_datasets} synthetic three-group "
                f"datasets of size {self.sample_size} per group "
                f"sweeping effect size from null to strong (seed={self.seed}), "
                f"``scipy.stats.f_oneway``, "
                f"``statsmodels.stats.anova.anova_lm`` (via OLS), and "
                f"``pingouin.anova`` produce F-statistics AND two-sided "
                f"p-values that agree to ≤ {self.tolerance:g} across "
                f"all pairwise comparisons. (RFC 0002 Phase E1: "
                f"cross-framework validation; three-way ANOVA variant.)"
            ),
            operationalization=(
                "Generate N three-group datasets where each group has "
                "size n and is drawn from Normal(μ_g, σ²) for a sweep "
                "of (μ_0, μ_1, μ_2) configurations including null "
                "(all μ equal) and alternatives. Compute F and "
                "two-sided p under scipy.stats.f_oneway, "
                "statsmodels OLS+anova_lm, and pingouin.anova. "
                "Compute max_abs_diff = max over (dataset, statistic "
                "∈ {F, p}, backend-pair) of |stat_a - stat_b|. "
                "VALIDATED iff max_abs_diff ≤ tolerance."
            ),
            threshold=Threshold(
                metric="max_absolute_anova_difference",
                comparator="<=",
                value=self.tolerance,
                units="F_or_p",
            ),
            h0=(
                "At least one backend pair disagrees on the ANOVA F "
                "statistic OR the two-sided p value by more than the "
                "floating-point tolerance."
            ),
            h1=(
                "All three backends compute identical F AND p to "
                "floating-point tolerance across every dataset."
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
            import pandas as pd
            import pingouin
            import scipy
            import statsmodels
            import statsmodels.formula.api as smf
            from scipy.stats import f_oneway
            from statsmodels.stats.anova import anova_lm
        except ImportError as exc:
            raise RuntimeError(
                "OneWayAnovaCrosscheckScenario requires scipy + "
                "statsmodels + pingouin + pandas. Install via "
                "`pip install 'ophamin[analytic]'`. "
                f"({exc})"
            ) from exc

        rng = np.random.default_rng(self.seed)
        # Sweep effect magnitude across [0, 1.5] so half the datasets
        # are near-null (small F, large p) and half are clearly
        # alternative (large F, small p). The pairwise agreement
        # contract must hold in every regime.
        effect_magnitudes = np.linspace(0.0, 1.5, self.n_datasets)

        max_abs_diff = 0.0
        worst_pair_label = ""
        worst_statistic = ""
        per_dataset: list[dict[str, Any]] = []
        for i in range(self.n_datasets):
            eff = float(effect_magnitudes[i])
            g0 = rng.standard_normal(self.sample_size)
            g1 = eff + rng.standard_normal(self.sample_size)
            g2 = 2.0 * eff + rng.standard_normal(self.sample_size)

            # Backend A — scipy
            F_scipy, p_scipy = f_oneway(g0, g1, g2)
            F_scipy = float(F_scipy)
            p_scipy = float(p_scipy)

            # Backend B — statsmodels via OLS + anova_lm (Type II SS)
            df = pd.DataFrame({
                "value": np.concatenate([g0, g1, g2]),
                "group": (
                    ["A"] * self.sample_size
                    + ["B"] * self.sample_size
                    + ["C"] * self.sample_size
                ),
            })
            ols = smf.ols("value ~ C(group)", data=df).fit()
            aov = anova_lm(ols, typ=2)
            F_sm = float(aov["F"]["C(group)"])
            p_sm = float(aov["PR(>F)"]["C(group)"])

            # Backend C — pingouin.anova
            pg = pingouin.anova(data=df, dv="value", between="group")
            F_pg = float(pg["F"].iloc[0])
            p_pg = float(pg["p_unc"].iloc[0])

            dF_ss = abs(F_scipy - F_sm)
            dF_sp = abs(F_scipy - F_pg)
            dF_np = abs(F_sm - F_pg)
            dp_ss = abs(p_scipy - p_sm)
            dp_sp = abs(p_scipy - p_pg)
            dp_np = abs(p_sm - p_pg)

            local_max = max(dF_ss, dF_sp, dF_np, dp_ss, dp_sp, dp_np)
            if local_max > max_abs_diff:
                max_abs_diff = local_max
                labels = [
                    ("F", "scipy_vs_statsmodels", dF_ss),
                    ("F", "scipy_vs_pingouin", dF_sp),
                    ("F", "statsmodels_vs_pingouin", dF_np),
                    ("p", "scipy_vs_statsmodels", dp_ss),
                    ("p", "scipy_vs_pingouin", dp_sp),
                    ("p", "statsmodels_vs_pingouin", dp_np),
                ]
                worst = max(labels, key=lambda lp: lp[2])
                worst_statistic, worst_pair_label, _ = worst

            if i < 5 or local_max > self.tolerance:
                per_dataset.append({
                    "i": i,
                    "effect_magnitude": eff,
                    "F_scipy": F_scipy,
                    "F_statsmodels": F_sm,
                    "F_pingouin": F_pg,
                    "p_scipy": p_scipy,
                    "p_statsmodels": p_sm,
                    "p_pingouin": p_pg,
                    "max_pair_diff": local_max,
                })

        agrees = max_abs_diff <= self.tolerance

        config = {
            "scenario": self.name,
            "n_datasets": self.n_datasets,
            "sample_size": self.sample_size,
            "seed": self.seed,
            "tolerance": self.tolerance,
        }
        dataset = DatasetRef(
            name=self.corpus_name,
            content_hash=content_hash(config),
            n_records=self.n_datasets,
            source=f"numpy.random.default_rng(seed={self.seed})",
            kind="synthetic-anova-three-group",
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
                f"{self.n_datasets} datasets × 3 backends × 2 "
                f"statistics; max pairwise |Δ| = {max_abs_diff:.3e} "
                f"on ({worst_statistic}, {worst_pair_label or 'none'}) "
                f"({'≤' if agrees else '>'} {self.tolerance:.0e} tol)"
            ),
        )

        evidence = [
            PillarEvidence(
                pillar="anova_scipy_vs_statsmodels_vs_pingouin",
                statistic_name="max_absolute_anova_difference",
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
                        f"— three-way one-way ANOVA agreement on "
                        f"both the F-statistic and the two-sided "
                        f"p-value"
                    ),
                    "scipy_version": getattr(scipy, "__version__", "unknown"),
                    "statsmodels_version": getattr(
                        statsmodels, "__version__", "unknown"
                    ),
                    "pingouin_version": getattr(
                        pingouin, "__version__", "unknown"
                    ),
                    "n_datasets": self.n_datasets,
                    "sample_size": self.sample_size,
                    "seed": self.seed,
                    "tolerance": self.tolerance,
                    "max_abs_diff": max_abs_diff,
                    "worst_statistic": worst_statistic,
                    "worst_pair": worst_pair_label,
                    "sample_datasets": per_dataset,
                },
            ),
        ]

        prov = ProvenanceGraph()
        agent_ophamin = prov.agent(
            "ophamin", role="experimentation_framework", version=__version__
        )
        agent_scipy = prov.agent(
            "scipy", role="anova_backend_a",
            version=getattr(scipy, "__version__", "unknown"),
        )
        agent_sm = prov.agent(
            "statsmodels", role="anova_backend_b_independent",
            version=getattr(statsmodels, "__version__", "unknown"),
        )
        agent_pg = prov.agent(
            "pingouin", role="anova_backend_c_oracle",
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
            n_datasets=self.n_datasets,
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

                command=self._build_reproduction_command(),

            ),
            provenance=prov.to_prov_json(),
            ophamin_version=__version__,
            ophamin_git_commit=capture_git_commit(_ophamin_project_root()),
        )
        proof.sign(sign_key)
        return proof

    def analysis_plan(self) -> str:
        return (
            f"Generate {self.n_datasets} three-group datasets of size "
            f"{self.sample_size} per group, sweeping effect magnitude "
            f"from null to 1.5σ, seed={self.seed}. Compute F and "
            f"two-sided p under scipy.stats.f_oneway, statsmodels "
            f"OLS+anova_lm (Type II SS), and pingouin.anova. For each "
            f"dataset, compute all six pairwise distances (3 backend "
            f"pairs × 2 statistics). Track the maximum. VALIDATED iff "
            f"max_abs_diff ≤ {self.tolerance:g}."
        )


__all__ = ["OneWayAnovaCrosscheckScenario"]
