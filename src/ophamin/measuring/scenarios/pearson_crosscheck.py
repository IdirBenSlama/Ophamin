"""scipy ↔ numpy ↔ pingouin Pearson-correlation cross-check (RFC 0002 Phase E1.4).

Pearson product-moment correlation is the load-bearing parametric
correlation primitive across the Ophamin pillar dep tree. Three
independent implementations are reachable from `[analytic]`:

* :func:`scipy.stats.pearsonr(x, y)` — the canonical scipy entry; uses
  a numerically-stable formulation with explicit Welford-style mean
  centering.
* :func:`numpy.corrcoef(x, y)[0, 1]` — the linear-algebra implementation
  in numpy core; computes via the covariance matrix.
* :func:`pingouin.corr(x, y, method='pearson')` — the
  effect-size-rich pillar wrapper; delegates to scipy under the hood
  but adds bootstrap CIs + power calculations on top.

All three compute the same statistic from the same data. They MUST
agree to floating-point tolerance. Three-way agreement is a tighter
constraint than the two-way Spearman cross-check (E1.3) — any pair-
wise drift surfaces, not just scipy-vs-pingouin.

VALIDATED iff every pair agrees across every backend pair (3 pairs ×
N samples). REFUTED if any backend disagrees.

Reference: RFC 0002 §3.1 E1 ("cross-framework validation studies").
This is the fourth shipped cross-framework check (after PyMC↔NumPyro
Bayesian, Wilson CI scipy↔statsmodels, Spearman scipy↔pingouin), each
covering a different statistical primitive.
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


@Stable(since="0.14.0", notes="RFC-0002 Phase E1.4 — three-way Pearson cross-framework validation.")
class PearsonCrosscheckScenario(Scenario):
    """scipy vs numpy vs pingouin Pearson correlation cross-check.

    Generates N ``(x, y)`` pairs of size ``sample_size`` with target
    correlations sweeping [-0.9, 0.9] from a fixed seed. For each pair,
    computes Pearson r under all three backends. Asserts every pairwise
    comparison agrees within ``tolerance``.

    Args:
        n_pairs: number of ``(x, y)`` pairs to generate. Default 30.
        sample_size: number of observations per pair. Default 100.
        seed: deterministic seed for the pair generator.
        tolerance: maximum allowed absolute difference between any
            two backends' Pearson r. Default 1e-9. The two scipy/numpy
            paths use different numerical formulations (covariance
            matrix vs centered-product); agreement at ≤ 1e-9 across
            both regimes is a strong empirical signal that neither has
            silently regressed.
    """

    name = "pearson-crosscheck"
    tier = Tier.MEASUREMENT_MACHINERY
    family = "cross_framework"
    goal = (
        "Verify the Pearson product-moment correlation implementations "
        "Ophamin depends on (scipy / numpy / pingouin) all produce the "
        "same value to floating-point tolerance across 30 (x, y) pairs."
    )
    explanation = (
        "Pearson r underpins regression diagnostics, drift detection, "
        "and any downstream pillar that talks about linear association. "
        "scipy.stats.pearsonr, numpy.corrcoef, and pingouin.corr each "
        "reach the same statistic via a different numerical path. "
        "Three-way agreement at machine epsilon is the strongest "
        "empirical signal that none has drifted from spec."
    )
    method = "cross_framework_oracle"
    falsification_consequence = (
        "scipy / numpy / pingouin disagree on Pearson r by more than "
        "the documented float-precision tolerance — at least one has "
        "regressed (e.g. broken numerical stability in the covariance "
        "path, or a default-parameter drift)."
    )
    corpus_name = "synthetic-correlated-pairs-pearson"
    target = "scipy+numpy+pingouin-cross-framework"

    def __init__(
        self,
        *,
        n_pairs: int = 30,
        sample_size: int = 100,
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
            "PearsonCrosscheckScenario uses a custom run(); "
            "score() is unreachable."
        )

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                f"Across {self.n_pairs} synthetic (x, y) pairs of size "
                f"{self.sample_size} (seed={self.seed}), "
                f"``scipy.stats.pearsonr``, ``numpy.corrcoef``, and "
                f"``pingouin.corr(method='pearson')`` produce Pearson r "
                f"values that agree to ≤ {self.tolerance:g} across "
                f"all three pairwise comparisons. "
                f"(RFC 0002 Phase E1: cross-framework validation at "
                f"the statistical-primitive layer; three-way variant.)"
            ),
            operationalization=(
                "Generate N (x, y) pairs where x ~ Normal(0, 1) and "
                "y = ρ_target × x + sqrt(1 - ρ_target²) × Normal(0, 1) "
                "for a sweep of ρ_target across [-0.9, 0.9]. Compute "
                "Pearson r under each of scipy, numpy, pingouin. Compute "
                "max_abs_diff = max over (pair, backend-comparison) of "
                "|r_a - r_b|. VALIDATED iff max_abs_diff ≤ tolerance "
                "across all three pairwise comparisons."
            ),
            threshold=Threshold(
                metric="max_absolute_pearson_difference",
                comparator="<=",
                value=self.tolerance,
                units="correlation",
            ),
            h0=(
                "At least one backend pair (scipy↔numpy, scipy↔pingouin, "
                "numpy↔pingouin) disagrees on Pearson r by more than "
                "the floating-point tolerance."
            ),
            h1=(
                "All three backends compute identical Pearson r to "
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
            from scipy.stats import pearsonr
        except ImportError as exc:
            raise RuntimeError(
                "PearsonCrosscheckScenario requires scipy + numpy + "
                "pingouin. Install via `pip install 'ophamin[analytic]'`. "
                f"({exc})"
            ) from exc

        rng = np.random.default_rng(self.seed)
        target_rhos = np.linspace(-0.9, 0.9, self.n_pairs)

        max_abs_diff = 0.0
        worst_pair_label = ""
        per_pair: list[dict[str, Any]] = []
        for i, rho_target in enumerate(target_rhos):
            x = rng.standard_normal(self.sample_size)
            noise = rng.standard_normal(self.sample_size)
            y = rho_target * x + np.sqrt(1.0 - rho_target ** 2) * noise

            # Backend A: scipy.stats.pearsonr
            scipy_result = pearsonr(x, y)
            r_scipy = float(scipy_result.statistic)

            # Backend B: numpy.corrcoef
            r_numpy = float(np.corrcoef(x, y)[0, 1])

            # Backend C: pingouin.corr(method='pearson')
            pingouin_result = pingouin.corr(x, y, method="pearson")
            r_pingouin = float(pingouin_result["r"].iloc[0])

            d_scipy_numpy = abs(r_scipy - r_numpy)
            d_scipy_pingouin = abs(r_scipy - r_pingouin)
            d_numpy_pingouin = abs(r_numpy - r_pingouin)
            local_max = max(d_scipy_numpy, d_scipy_pingouin, d_numpy_pingouin)
            if local_max > max_abs_diff:
                max_abs_diff = local_max
                if local_max == d_scipy_numpy:
                    worst_pair_label = "scipy_vs_numpy"
                elif local_max == d_scipy_pingouin:
                    worst_pair_label = "scipy_vs_pingouin"
                else:
                    worst_pair_label = "numpy_vs_pingouin"
            if i < 5 or local_max > self.tolerance:
                per_pair.append({
                    "i": i,
                    "rho_target": float(rho_target),
                    "r_scipy": r_scipy,
                    "r_numpy": r_numpy,
                    "r_pingouin": r_pingouin,
                    "d_scipy_numpy": d_scipy_numpy,
                    "d_scipy_pingouin": d_scipy_pingouin,
                    "d_numpy_pingouin": d_numpy_pingouin,
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
            kind="synthetic-correlated-pairs",
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
                f"{self.n_pairs} pairs × 3 backends; max pairwise "
                f"|Δr| = {max_abs_diff:.3e} on {worst_pair_label or 'none'} "
                f"({'≤' if agrees else '>'} {self.tolerance:.0e} tol)"
            ),
        )

        evidence = [
            PillarEvidence(
                pillar="pearson_scipy_vs_numpy_vs_pingouin",
                statistic_name="max_absolute_pearson_difference",
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
                        f"vs numpy {getattr(np, '__version__', 'unknown')} "
                        f"vs pingouin {getattr(pingouin, '__version__', 'unknown')} "
                        f"— three-way Pearson r agreement"
                    ),
                    "scipy_version": getattr(scipy, "__version__", "unknown"),
                    "numpy_version": getattr(np, "__version__", "unknown"),
                    "pingouin_version": getattr(pingouin, "__version__", "unknown"),
                    "n_pairs": self.n_pairs,
                    "sample_size": self.sample_size,
                    "seed": self.seed,
                    "tolerance": self.tolerance,
                    "max_abs_diff": max_abs_diff,
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
            "scipy", role="pearson_backend_a",
            version=getattr(scipy, "__version__", "unknown"),
        )
        agent_numpy = prov.agent(
            "numpy", role="pearson_backend_b",
            version=getattr(np, "__version__", "unknown"),
        )
        agent_pingouin = prov.agent(
            "pingouin", role="pearson_backend_c_oracle",
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
        prov.was_associated_with(activity, agent_numpy)
        prov.was_associated_with(activity, agent_pingouin)
        prov.was_generated_by(result_entity, activity)
        prov.was_derived_from(result_entity, data_entity)

        proof = EmpiricalProofRecord(
            claim=claim,
            preregistration=prereg,
            datasets=[dataset],
            substrate_name="scipy+numpy+pingouin-cross-framework",
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
            f"Generate {self.n_pairs} (x, y) pairs of size "
            f"{self.sample_size} with target Pearson correlations "
            f"sweeping [-0.9, 0.9], seed={self.seed}. Compute Pearson r "
            f"under scipy.stats.pearsonr, numpy.corrcoef, and "
            f"pingouin.corr(method='pearson'). For each pair, compute "
            f"the three pairwise absolute differences. Track the "
            f"maximum. VALIDATED iff max_abs_diff ≤ {self.tolerance:g}."
        )


__all__ = ["PearsonCrosscheckScenario"]
