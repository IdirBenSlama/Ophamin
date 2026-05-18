"""scipy ↔ statsmodels Wilson-CI cross-check (RFC 0002 Phase E1.2).

The Wilson confidence interval for a binomial proportion is the
default CI shape Ophamin uses across every scenario that reports a
proportion (`crdt-laws`, `concentrated-immune-siege`, etc.). It
appears in the proof codec's `PillarEvidence.ci_low/ci_high` fields.

Two independent implementations are reachable from the framework's
dep tree:

* :func:`scipy.stats.binomtest(k, n).proportion_ci(...)` —
  Wilson by default (`method='wilson'`) in scipy ≥ 1.7.
* :func:`statsmodels.stats.proportion.proportion_confint(k, n,
  method='wilson')` — same statistic via the statsmodels code path
  the framework uses today.

Numerically the two MUST agree to within floating-point tolerance:
Wilson CI has a closed-form solution; both implementations evaluate
the same formula. Disagreement would mean one of:

1. a library defect in either scipy or statsmodels (real bug);
2. the framework's expectations about ``proportion_confint``'s
   defaults are wrong (silent semantic drift).

This scenario picks 100 ``(k, n)`` pairs from a deterministic seed,
computes the 95 % Wilson CI under both backends, and asserts every
pair agrees to ≤ 1e-9 on both bounds.

VALIDATED iff every pair agrees. REFUTED if any pair disagrees by
more than ``tolerance``.

Reference: RFC 0002 §3.1 E1 ("cross-framework validation studies");
RFC 0002 §3.1 lists this as one of the three "Pillar-class
scenarios cross-checked against R / Stan / PyMC" — the Wilson-CI
check is the closest framework-internal equivalent at the
statistical-primitive level.
"""

from __future__ import annotations

import random
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


@Stable(since="0.13.0", notes="RFC-0002 Phase E1 second cross-framework validation.")
class WilsonCICrosscheckScenario(Scenario):
    """scipy vs statsmodels Wilson confidence interval cross-check.

    Generates N random ``(k, n)`` pairs with a fixed seed. For each,
    computes the 95 % Wilson CI under both backends. Asserts every
    pair agrees within ``tolerance`` (absolute difference) on both
    the lower and upper bound.

    Args:
        n_pairs: how many ``(k, n)`` pairs to generate. Default 100.
        max_n: cap on per-pair sample size. Default 1000.
        seed: deterministic seed for both the pair generator + the
            backend invocations.
        tolerance: maximum allowed absolute difference on either CI
            bound between the two backends. Default 1e-9 — Wilson CI
            is closed-form, so both implementations should agree to
            float64 precision modulo the libraries' internal
            numerical rounding.
        confidence: 1 − α for the CI. Default 0.95.
    """

    name = "wilson-ci-crosscheck"
    tier = Tier.MEASUREMENT_MACHINERY
    family = "cross_framework"
    goal = (
        "Verify the Wilson confidence-interval implementation Ophamin "
        "depends on by computing the same CI under scipy and "
        "statsmodels and asserting they agree to floating-point "
        "tolerance across 100 (k, n) pairs."
    )
    explanation = (
        "Wilson CI is the default proportion-CI shape Ophamin emits "
        "across every scenario that reports a proportion. Both scipy "
        "and statsmodels expose Wilson CI via independent code paths "
        "from the same closed-form formula. They MUST agree to "
        "floating-point tolerance; disagreement surfaces either a "
        "library defect or silent semantic drift in the framework's "
        "expectations about defaults."
    )
    method = "cross_framework_oracle"
    falsification_consequence = (
        "scipy and statsmodels disagree on Wilson CI bounds by more "
        "than the documented float-precision tolerance — at least "
        "one library has a defect, or the framework is calling one "
        "of them with non-default arguments it didn't realize were "
        "different."
    )
    corpus_name = "synthetic-binomial-pairs"
    target = "scipy+statsmodels-cross-framework"

    def __init__(
        self,
        *,
        n_pairs: int = 100,
        max_n: int = 1000,
        seed: int = 20260518,
        tolerance: float = 1e-9,
        confidence: float = 0.95,
    ) -> None:
        if n_pairs < 1:
            raise ValueError(f"n_pairs must be ≥ 1, got {n_pairs}")
        if max_n < 2:
            raise ValueError(f"max_n must be ≥ 2, got {max_n}")
        if tolerance <= 0.0:
            raise ValueError(f"tolerance must be > 0, got {tolerance}")
        if not 0.0 < confidence < 1.0:
            raise ValueError(
                f"confidence must be in (0, 1), got {confidence}"
            )
        self.n_pairs = int(n_pairs)
        self.max_n = int(max_n)
        self.seed = int(seed)
        self.tolerance = float(tolerance)
        self.confidence = float(confidence)
        self.n_cycles = 0

    def score(
        self,
        cycle_results: list[CycleResult],
        records: list[CorpusRecord],
    ) -> ScenarioScore:
        raise NotImplementedError(
            "WilsonCICrosscheckScenario uses a custom run(); "
            "score() is unreachable."
        )

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                f"Across {self.n_pairs} random (k, n) binomial pairs "
                f"(seed={self.seed}, max_n={self.max_n}), scipy's "
                f"``binomtest.proportion_ci(method='wilson')`` and "
                f"statsmodels's ``proportion_confint(method='wilson')`` "
                f"produce {self.confidence:.0%} CI bounds that agree "
                f"to ≤ {self.tolerance:g} on both lower and upper "
                f"endpoints. (RFC 0002 Phase E1: cross-framework "
                f"validation at the statistical-primitive layer.)"
            ),
            operationalization=(
                "Generate N pairs (k, n) with k ~ Uniform(0, n), n ~ "
                "Uniform(2, max_n). For each pair, compute the Wilson "
                "CI at the configured confidence under both backends. "
                "Compute max_abs_diff = max over pairs of "
                "max(|low_scipy - low_sm|, |high_scipy - high_sm|). "
                "VALIDATED iff max_abs_diff ≤ tolerance."
            ),
            threshold=Threshold(
                metric="max_absolute_ci_difference",
                comparator="<=",
                value=self.tolerance,
                units="proportion",
            ),
            h0=(
                "scipy and statsmodels disagree on the Wilson CI by "
                "more than the floating-point tolerance — at least one "
                "implementation has a defect."
            ),
            h1=(
                "Both libraries evaluate the same closed-form Wilson "
                "CI and produce identical bounds to floating-point "
                "tolerance."
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
            from scipy.stats import binomtest
            from statsmodels.stats.proportion import proportion_confint
            import scipy
            import statsmodels
        except ImportError as exc:
            raise RuntimeError(
                "WilsonCICrosscheckScenario requires scipy + statsmodels. "
                f"Both are in the default install. ({exc})"
            ) from exc

        rng = random.Random(self.seed)
        alpha = 1.0 - self.confidence

        max_low_diff = 0.0
        max_high_diff = 0.0
        per_pair: list[dict[str, Any]] = []
        for i in range(self.n_pairs):
            n = rng.randint(2, self.max_n)
            k = rng.randint(0, n)
            # scipy
            scipy_ci = binomtest(k, n).proportion_ci(
                confidence_level=self.confidence, method="wilson"
            )
            low_scipy = float(scipy_ci.low)
            high_scipy = float(scipy_ci.high)
            # statsmodels
            sm_low, sm_high = proportion_confint(
                count=k, nobs=n, alpha=alpha, method="wilson"
            )
            low_sm = float(sm_low)
            high_sm = float(sm_high)
            # diffs
            low_diff = abs(low_scipy - low_sm)
            high_diff = abs(high_scipy - high_sm)
            max_low_diff = max(max_low_diff, low_diff)
            max_high_diff = max(max_high_diff, high_diff)
            # Record the first 5 + any pair that exceeds tolerance.
            if i < 5 or low_diff > self.tolerance or high_diff > self.tolerance:
                per_pair.append({
                    "i": i, "k": k, "n": n,
                    "scipy_low": low_scipy, "scipy_high": high_scipy,
                    "sm_low": low_sm, "sm_high": high_sm,
                    "low_diff": low_diff, "high_diff": high_diff,
                })

        max_abs_diff = max(max_low_diff, max_high_diff)
        agrees = max_abs_diff <= self.tolerance

        config = {
            "scenario": self.name,
            "n_pairs": self.n_pairs,
            "max_n": self.max_n,
            "seed": self.seed,
            "tolerance": self.tolerance,
            "confidence": self.confidence,
        }
        dataset = DatasetRef(
            name=self.corpus_name,
            content_hash=content_hash(config),
            n_records=self.n_pairs,
            source=f"random.Random(seed={self.seed})",
            kind="synthetic-binomial-pairs",
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
                f"{self.n_pairs} pairs checked; max |low_scipy - low_sm| = "
                f"{max_low_diff:.3e}; max |high_scipy - high_sm| = "
                f"{max_high_diff:.3e}; max overall = {max_abs_diff:.3e} "
                f"({'≤' if agrees else '>'} {self.tolerance:.0e} tol)"
            ),
        )

        evidence = [
            PillarEvidence(
                pillar="wilson_ci_scipy_vs_statsmodels",
                statistic_name="max_absolute_ci_difference",
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
                        f"scipy {getattr(scipy, '__version__', 'unknown')} vs "
                        f"statsmodels {getattr(statsmodels, '__version__', 'unknown')} "
                        f"— both implement closed-form Wilson CI"
                    ),
                    "scipy_version": getattr(scipy, "__version__", "unknown"),
                    "statsmodels_version": getattr(statsmodels, "__version__", "unknown"),
                    "n_pairs": self.n_pairs,
                    "max_n": self.max_n,
                    "seed": self.seed,
                    "confidence": self.confidence,
                    "tolerance": self.tolerance,
                    "max_low_diff": max_low_diff,
                    "max_high_diff": max_high_diff,
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
            "scipy", role="ci_backend_a",
            version=getattr(scipy, "__version__", "unknown"),
        )
        agent_sm = prov.agent(
            "statsmodels", role="ci_backend_b_oracle",
            version=getattr(statsmodels, "__version__", "unknown"),
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
        prov.was_generated_by(result_entity, activity)
        prov.was_derived_from(result_entity, data_entity)

        proof = EmpiricalProofRecord(
            claim=claim,
            preregistration=prereg,
            datasets=[dataset],
            substrate_name="scipy+statsmodels-cross-framework",
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
            f"Generate {self.n_pairs} random (k, n) binomial pairs with "
            f"seed={self.seed}, n ∈ [2, {self.max_n}]. For each compute "
            f"the {self.confidence:.0%} Wilson CI under scipy "
            f"(binomtest.proportion_ci) AND statsmodels "
            f"(proportion_confint). Track the maximum absolute "
            f"difference on both CI bounds across pairs. VALIDATED iff "
            f"max_abs_diff ≤ {self.tolerance:g}."
        )


__all__ = ["WilsonCICrosscheckScenario"]
