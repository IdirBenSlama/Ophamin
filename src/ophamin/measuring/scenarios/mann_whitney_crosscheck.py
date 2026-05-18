"""scipy ↔ pingouin Mann-Whitney U cross-check (RFC 0002 Phase E1.7).

The two-sample Mann-Whitney U test (Wilcoxon rank-sum) is the
non-parametric counterpart to Welch's two-sample t-test. It is the
load-bearing primitive whenever an Ophamin pillar makes a
between-group claim under non-normality or ordinal data. Two
independent implementations are reachable from ``[analytic]``:

* :func:`scipy.stats.mannwhitneyu(x, y, alternative='two-sided',
  use_continuity=True)` — scipy's canonical entry.
* :func:`pingouin.mwu(x, y, alternative='two-sided')` — the
  effect-size-rich wrapper. Defaults to ``use_continuity=True``
  matching scipy.

Both compute the same U statistic and two-sided p-value from the
same data under the same continuity-correction setting. They MUST
agree to floating-point tolerance.

VALIDATED iff every pairwise comparison agrees across N samples on
both the U statistic and the p value. REFUTED if either disagrees.

Reference: RFC 0002 §3.1 E1 ("cross-framework validation studies").
Seventh shipped cross-framework check; first non-parametric
hypothesis-testing cross-check (the five before it cover
parametric and Bayesian primitives). Closes the most heavily-
exercised gap in scipy.stats coverage by the Ophamin pillar tree.
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


@Stable(since="0.15.0", notes="RFC-0002 Phase E1.7 — non-parametric Mann-Whitney U cross-framework validation.")
class MannWhitneyUCrosscheckScenario(Scenario):
    """scipy vs pingouin Mann-Whitney U test cross-check.

    Generates N ``(x, y)`` independent-sample pairs from a fixed
    seed, drawing from a mix of normal, log-normal, and Cauchy
    distributions so the cross-check exercises both light- and
    heavy-tailed regimes (where rank-based statistics matter most).
    For each pair, computes the U statistic AND the two-sided p
    value under both backends with ``use_continuity=True``. Asserts
    every pair agrees within ``tolerance`` on BOTH statistics.

    Args:
        n_pairs: number of independent ``(x, y)`` sample pairs.
            Default 30.
        sample_size: observations per group. Default 50.
        seed: deterministic seed for the pair generator.
        tolerance: maximum allowed absolute pairwise difference.
            Default 1e-9. Empirically both backends agree exactly
            on U (rank sums are integer-valued) and at ~5e-16 on
            the two-sided p value under matched continuity settings.
    """

    name = "mann-whitney-crosscheck"
    tier = Tier.MEASUREMENT_MACHINERY
    family = "cross_framework"
    goal = (
        "Verify the Mann-Whitney U test implementations Ophamin "
        "depends on (scipy / pingouin) produce identical U statistics "
        "and two-sided p-values to floating-point tolerance across "
        "30 independent-sample pairs drawn from a mix of "
        "distributions."
    )
    explanation = (
        "Mann-Whitney U is the rank-based two-sample test that the "
        "Ophamin pillar tree falls back to whenever a means-"
        "difference claim cannot assume normality. scipy.stats."
        "mannwhitneyu and pingouin.mwu compute the same U via "
        "independent code paths (pingouin does NOT delegate to "
        "scipy). Both default to use_continuity=True; the cross-"
        "check pins both at that setting and asserts U + p "
        "agreement to floating-point tolerance."
    )
    method = "cross_framework_oracle"
    falsification_consequence = (
        "scipy and pingouin disagree on the Mann-Whitney U statistic "
        "or two-sided p-value by more than the documented float-"
        "precision tolerance — at least one library has a defect in "
        "the rank-sum calculation, the tie-correction handling, or "
        "the asymptotic normal approximation."
    )
    corpus_name = "synthetic-mann-whitney-mixed-distributions"
    target = "scipy+pingouin-cross-framework"

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
            "MannWhitneyUCrosscheckScenario uses a custom run(); "
            "score() is unreachable."
        )

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                f"Across {self.n_pairs} synthetic (x, y) sample pairs "
                f"of size {self.sample_size} per group drawn from a "
                f"rotation of normal, log-normal, and Cauchy "
                f"distributions with varying shift parameters "
                f"(seed={self.seed}), "
                f"``scipy.stats.mannwhitneyu(use_continuity=True)`` "
                f"and ``pingouin.mwu`` produce Mann-Whitney U "
                f"statistics AND two-sided p-values that agree to ≤ "
                f"{self.tolerance:g} across every pair. (RFC 0002 "
                f"Phase E1: cross-framework validation; first "
                f"non-parametric variant.)"
            ),
            operationalization=(
                "Generate N (x, y) pairs cycling through three "
                "distribution shapes (Normal(0,1), LogNormal(0,1), "
                "Cauchy(0,1)) with a sweep of location shifts. For "
                "each pair, compute Mann-Whitney U + two-sided p "
                "under both backends with use_continuity=True. "
                "Compute max_abs_diff = max over (pair, statistic ∈ "
                "{U, p}) of |stat_scipy - stat_pingouin|. "
                "VALIDATED iff max_abs_diff ≤ tolerance."
            ),
            threshold=Threshold(
                metric="max_absolute_mannwhitneyu_difference",
                comparator="<=",
                value=self.tolerance,
                units="U_or_p",
            ),
            h0=(
                "scipy and pingouin disagree on Mann-Whitney U OR the "
                "two-sided p-value by more than the floating-point "
                "tolerance under matched continuity settings."
            ),
            h1=(
                "Both backends compute identical U AND p to "
                "floating-point tolerance across every pair."
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
            from scipy.stats import mannwhitneyu
        except ImportError as exc:
            raise RuntimeError(
                "MannWhitneyUCrosscheckScenario requires scipy + "
                "pingouin. Install via `pip install 'ophamin[analytic]'`. "
                f"({exc})"
            ) from exc

        rng = np.random.default_rng(self.seed)
        # Rotate three distribution shapes so each backend pair must
        # agree under all three. Shifts sweep [-1, 1].
        shifts = np.linspace(-1.0, 1.0, self.n_pairs)
        shapes = ["normal", "lognormal", "cauchy"]

        max_abs_diff = 0.0
        worst_statistic = ""
        per_pair: list[dict[str, Any]] = []
        for i in range(self.n_pairs):
            shift = float(shifts[i])
            shape = shapes[i % len(shapes)]
            if shape == "normal":
                x = rng.standard_normal(self.sample_size)
                y = shift + rng.standard_normal(self.sample_size)
            elif shape == "lognormal":
                x = rng.lognormal(0.0, 1.0, self.sample_size)
                y = shift + rng.lognormal(0.0, 1.0, self.sample_size)
            else:  # cauchy
                x = rng.standard_cauchy(self.sample_size)
                y = shift + rng.standard_cauchy(self.sample_size)

            # Backend A — scipy with continuity correction (matches
            # pingouin's default)
            ra = mannwhitneyu(
                x, y, alternative="two-sided", use_continuity=True
            )
            U_scipy = float(ra.statistic)
            p_scipy = float(ra.pvalue)

            # Backend B — pingouin
            pg = pingouin.mwu(x, y, alternative="two-sided")
            U_pg = float(pg["U_val"].iloc[0])
            p_pg = float(pg["p_val"].iloc[0])

            dU = abs(U_scipy - U_pg)
            dp = abs(p_scipy - p_pg)
            local_max = max(dU, dp)
            if local_max > max_abs_diff:
                max_abs_diff = local_max
                worst_statistic = "U" if dU >= dp else "p"

            if i < 5 or local_max > self.tolerance:
                per_pair.append({
                    "i": i,
                    "shape": shape,
                    "shift": shift,
                    "U_scipy": U_scipy,
                    "U_pingouin": U_pg,
                    "p_scipy": p_scipy,
                    "p_pingouin": p_pg,
                    "abs_U_diff": dU,
                    "abs_p_diff": dp,
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
            kind="synthetic-mann-whitney-mixed-distributions",
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
                f"{self.n_pairs} pairs × 2 backends × 2 statistics; "
                f"max pairwise |Δ| = {max_abs_diff:.3e} on "
                f"{worst_statistic or 'none'} "
                f"({'≤' if agrees else '>'} {self.tolerance:.0e} tol)"
            ),
        )

        evidence = [
            PillarEvidence(
                pillar="mann_whitney_u_scipy_vs_pingouin",
                statistic_name="max_absolute_mannwhitneyu_difference",
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
                        f"vs pingouin "
                        f"{getattr(pingouin, '__version__', 'unknown')} "
                        f"— two-way Mann-Whitney U agreement on both "
                        f"the U statistic and the two-sided p-value "
                        f"under matched use_continuity=True"
                    ),
                    "scipy_version": getattr(scipy, "__version__", "unknown"),
                    "pingouin_version": getattr(
                        pingouin, "__version__", "unknown"
                    ),
                    "n_pairs": self.n_pairs,
                    "sample_size": self.sample_size,
                    "seed": self.seed,
                    "tolerance": self.tolerance,
                    "max_abs_diff": max_abs_diff,
                    "worst_statistic": worst_statistic,
                    "distribution_shapes": shapes,
                    "sample_pairs": per_pair,
                },
            ),
        ]

        prov = ProvenanceGraph()
        agent_ophamin = prov.agent(
            "ophamin", role="experimentation_framework", version=__version__
        )
        agent_scipy = prov.agent(
            "scipy", role="mannwhitney_backend_a",
            version=getattr(scipy, "__version__", "unknown"),
        )
        agent_pg = prov.agent(
            "pingouin", role="mannwhitney_backend_b_oracle",
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
        prov.was_associated_with(activity, agent_pg)
        prov.was_generated_by(result_entity, activity)
        prov.was_derived_from(result_entity, data_entity)

        proof = EmpiricalProofRecord(
            claim=claim,
            preregistration=prereg,
            datasets=[dataset],
            substrate_name="scipy+pingouin-cross-framework",
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
            f"Generate {self.n_pairs} (x, y) sample pairs of size "
            f"{self.sample_size} per group, cycling through Normal / "
            f"LogNormal / Cauchy distributions with location shifts "
            f"sweeping [-1, 1], seed={self.seed}. Compute Mann-"
            f"Whitney U + two-sided p under scipy.stats.mannwhitneyu"
            f"(use_continuity=True) AND pingouin.mwu (same default). "
            f"For each pair, compute |ΔU| and |Δp|. Track the maximum "
            f"of either. VALIDATED iff max_abs_diff ≤ {self.tolerance:g}."
        )


__all__ = ["MannWhitneyUCrosscheckScenario"]
