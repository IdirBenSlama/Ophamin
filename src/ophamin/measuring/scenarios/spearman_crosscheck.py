"""scipy ↔ pingouin Spearman-correlation cross-check (RFC 0002 Phase E1.3).

Spearman rank correlation is a non-parametric primitive used across
multiple Ophamin scenarios + pillars (causal-discovery's PCMCI
backend, mixed-effects diagnostics, drift detection). Two independent
implementations are reachable from the framework's dep tree:

* :func:`scipy.stats.spearmanr(x, y)` — the canonical NumPy / SciPy
  implementation that most of Python statistics depends on.
* :func:`pingouin.corr(x, y, method='spearman')` — the
  effect-size-rich pillar wrapper in ``[analytic]``.

Both compute the same statistic from the same data; they MUST agree
to floating-point tolerance. Disagreement surfaces either an upstream
library defect or a silent change in default behaviour (e.g. how
tied ranks are handled).

This scenario picks 30 ``(x, y)`` pairs with various correlation
strengths from a deterministic seed, computes Spearman ρ under both
backends, and asserts every pair agrees to ≤ 1e-9.

VALIDATED iff every pair agrees. REFUTED if any pair drifts.

Reference: RFC 0002 §3.1 E1 ("cross-framework validation studies").
This is the third of three shipped cross-framework checks (after
PyMC↔NumPyro Bayesian + Wilson CI scipy↔statsmodels), satisfying
the RFC's "≥ 3 cross-framework validation proofs" acceptance
criterion.
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


@Stable(since="0.13.0", notes="RFC-0002 Phase E1 third cross-framework validation.")
class SpearmanCrosscheckScenario(Scenario):
    """scipy vs pingouin Spearman rank correlation cross-check.

    Generates N ``(x, y)`` pairs of size ``sample_size`` with varying
    correlation strengths from a fixed seed. For each pair, computes
    Spearman ρ under both backends. Asserts every pair agrees within
    ``tolerance``.

    Args:
        n_pairs: how many ``(x, y)`` pairs to generate. Default 30.
        sample_size: number of observations per pair. Default 100.
        seed: deterministic seed for the pair generator.
        tolerance: maximum allowed absolute difference between the
            two implementations' Spearman ρ. Default 1e-9 — both
            implementations compute rank correlation from the same
            formula; agreement at machine epsilon is expected.
    """

    name = "spearman-crosscheck"
    tier = Tier.MEASUREMENT_MACHINERY
    family = "cross_framework"
    goal = (
        "Verify the Spearman rank-correlation implementation Ophamin "
        "depends on by computing the same correlation under scipy "
        "and pingouin and asserting they agree to floating-point "
        "tolerance across 30 (x, y) pairs."
    )
    explanation = (
        "Spearman ρ is a non-parametric statistic used by Ophamin's "
        "causal-discovery + drift-detection + diagnostics pillars. "
        "scipy.stats.spearmanr and pingouin.corr(method='spearman') "
        "implement the same formula via independent code paths. They "
        "MUST agree to floating-point tolerance; disagreement signals "
        "either an upstream library defect or a silent default change."
    )
    method = "cross_framework_oracle"
    falsification_consequence = (
        "scipy and pingouin disagree on Spearman ρ by more than the "
        "documented float-precision tolerance — at least one library "
        "has a defect or a default behaviour drifted (e.g. tied-rank "
        "handling)."
    )
    corpus_name = "synthetic-correlated-pairs"
    target = "scipy+pingouin-cross-framework"

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
            "SpearmanCrosscheckScenario uses a custom run(); "
            "score() is unreachable."
        )

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                f"Across {self.n_pairs} synthetic (x, y) pairs of size "
                f"{self.sample_size} (seed={self.seed}), "
                f"``scipy.stats.spearmanr`` and "
                f"``pingouin.corr(method='spearman')`` produce Spearman "
                f"ρ values that agree to ≤ {self.tolerance:g}. "
                f"(RFC 0002 Phase E1: cross-framework validation at "
                f"the statistical-primitive layer.)"
            ),
            operationalization=(
                "Generate N (x, y) pairs where x ~ Normal(0, 1) and "
                "y = ρ_target × x + sqrt(1 - ρ_target²) × Normal(0, 1) "
                "for a sweep of ρ_target. Compute Spearman ρ under "
                "both backends. Compute max_abs_diff = max over pairs "
                "of |ρ_scipy - ρ_pingouin|. VALIDATED iff max_abs_diff "
                "≤ tolerance."
            ),
            threshold=Threshold(
                metric="max_absolute_spearman_difference",
                comparator="<=",
                value=self.tolerance,
                units="correlation",
            ),
            h0=(
                "scipy and pingouin disagree on Spearman ρ by more "
                "than the floating-point tolerance — at least one "
                "library has a defect or default-behaviour drift."
            ),
            h1=(
                "Both libraries compute identical Spearman ρ to "
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
            from scipy.stats import spearmanr
        except ImportError as exc:
            raise RuntimeError(
                "SpearmanCrosscheckScenario requires scipy + pingouin. "
                f"Install via `pip install 'ophamin[analytic]'`. ({exc})"
            ) from exc

        rng = np.random.default_rng(self.seed)
        # Sweep ρ_target across [-0.9, 0.9] to exercise both negative
        # and positive correlations.
        target_rhos = np.linspace(-0.9, 0.9, self.n_pairs)

        max_abs_diff = 0.0
        per_pair: list[dict[str, Any]] = []
        for i, rho_target in enumerate(target_rhos):
            x = rng.standard_normal(self.sample_size)
            noise = rng.standard_normal(self.sample_size)
            # y carries rho_target Pearson correlation; Spearman is
            # rank-correlation, so the observed Spearman won't equal
            # rho_target exactly but the two backends MUST agree on
            # whatever value they compute.
            y = rho_target * x + np.sqrt(1.0 - rho_target ** 2) * noise

            scipy_result = spearmanr(x, y)
            rho_scipy = float(scipy_result.statistic)

            pingouin_result = pingouin.corr(x, y, method="spearman")
            # pingouin returns a DataFrame; the rho column is "r".
            rho_pingouin = float(pingouin_result["r"].iloc[0])

            diff = abs(rho_scipy - rho_pingouin)
            max_abs_diff = max(max_abs_diff, diff)
            if i < 5 or diff > self.tolerance:
                per_pair.append({
                    "i": i,
                    "rho_target": float(rho_target),
                    "rho_scipy": rho_scipy,
                    "rho_pingouin": rho_pingouin,
                    "abs_diff": diff,
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
                f"{self.n_pairs} pairs checked; max |rho_scipy - "
                f"rho_pingouin| = {max_abs_diff:.3e} "
                f"({'≤' if agrees else '>'} {self.tolerance:.0e} tol)"
            ),
        )

        evidence = [
            PillarEvidence(
                pillar="spearman_scipy_vs_pingouin",
                statistic_name="max_absolute_spearman_difference",
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
                        f"vs pingouin {getattr(pingouin, '__version__', 'unknown')} "
                        f"— both implement Spearman ρ from the same formula"
                    ),
                    "scipy_version": getattr(scipy, "__version__", "unknown"),
                    "pingouin_version": getattr(pingouin, "__version__", "unknown"),
                    "n_pairs": self.n_pairs,
                    "sample_size": self.sample_size,
                    "seed": self.seed,
                    "tolerance": self.tolerance,
                    "max_abs_diff": max_abs_diff,
                    "sample_pairs": per_pair,
                },
            ),
        ]

        prov = ProvenanceGraph()
        agent_ophamin = prov.agent(
            "ophamin", role="experimentation_framework", version=__version__
        )
        agent_scipy = prov.agent(
            "scipy", role="spearman_backend_a",
            version=getattr(scipy, "__version__", "unknown"),
        )
        agent_pingouin = prov.agent(
            "pingouin", role="spearman_backend_b_oracle",
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
        prov.was_associated_with(activity, agent_pingouin)
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
            f"Generate {self.n_pairs} (x, y) pairs of size "
            f"{self.sample_size} with target Spearman correlations "
            f"sweeping [-0.9, 0.9], seed={self.seed}. Compute Spearman ρ "
            f"under scipy.stats.spearmanr AND pingouin.corr(method="
            f"'spearman'). Track the maximum absolute difference. "
            f"VALIDATED iff max_abs_diff ≤ {self.tolerance:g}."
        )


__all__ = ["SpearmanCrosscheckScenario"]
