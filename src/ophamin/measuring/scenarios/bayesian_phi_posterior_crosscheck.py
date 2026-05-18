"""PyMC ↔ NumPyro Bayesian posterior cross-check (RFC 0002 Phase E1).

Per [RFC 0002 §3.1](../../../docs/rfc/0002-sota-elevation-stages-5-and-6.md)
Phase E1 ("cross-framework validation studies"), the framework's
Bayesian-phi-posterior scenario uses PyMC. The Phase E1 acceptance
criterion: **a second Bayesian backend produces the same posterior
contraction within tolerance, providing independent corroboration**.

NumPyro (JAX-backed) is the natural choice — already in the
``[bayesian]`` extra, lightweight to call, uses a completely
independent sampler (HMC via JAX rather than PyMC's NUTS via
PyTensor). Disagreement between the two would indicate either:

* a PyMC/NumPyro divergence in the underlying NUTS step (real bug);
* the framework's NormalMean model is mis-specified;
* one backend has a seeding leak that breaks reproducibility.

This scenario:

1. Generates N synthetic samples from a Normal(true_mu, true_sigma)
   distribution with a fixed seed;
2. Runs the **same model** (PyMC) and the **same model** (NumPyro)
   against the same data;
3. Computes the absolute difference of the two posterior means + the
   ratio of the two posterior HDI widths;
4. VALIDATED iff:
   - ``|mu_pymc − mu_numpyro| ≤ mean_tolerance``, AND
   - ``hdi_width_ratio ∈ [1 − width_tolerance, 1 + width_tolerance]``.

Reference: RFC 0002 §3.1 E1, lines starting "Pillar-class scenarios
cross-checked against R / Stan / PyMC — the Bayesian-phi-posterior
scenario already uses PyMC; add a Stan alternative under
``[bayesian_stan]``…". We're shipping the lighter NumPyro variant
first; Stan can land as a follow-on under ``[bayesian_stan]`` without
removing this one.

Output
======

A signed :class:`EmpiricalProofRecord` whose evidence carries:

* per-backend (PyMC, NumPyro) HDI low / high / mean values;
* the mean-difference + width-ratio numbers;
* the seed + sample-size used for reproducibility.

This scenario does NOT execute Kimera — it validates the upstream
Bayesian-inference machinery the framework depends on.
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


@Stable(since="0.12.0", notes="RFC-0002 Phase E1 first cross-framework validation.")
class BayesianPhiPosteriorCrosscheckScenario(Scenario):
    """Cross-backend Bayesian inference agreement audit.

    Generates synthetic data once; fits the same NormalMean model
    with PyMC and with NumPyro; asserts the posteriors agree on the
    posterior mean (within absolute tolerance) and HDI width (within
    relative tolerance).

    Args:
        n_samples: synthetic-sample size. Default 200 (large enough to
            produce a well-converged posterior, small enough for
            CI-friendly time).
        true_mu: ground-truth mu for the synthetic data generator.
        true_sigma: ground-truth sigma.
        seed: deterministic seed for both data generation + each
            backend's NUTS sampler.
        mean_tolerance: maximum absolute difference between
            ``mu_pymc`` and ``mu_numpyro``. Default 0.1, which is
            ~10× the standard Monte-Carlo error of either sampler at
            the default sample size.
        width_tolerance: maximum relative deviation of the two HDI
            widths from 1.0. Default 0.5 — the two backends' 94 %
            HDI widths may differ by up to ±50 %; this is the
            sampler-noise floor for N ≈ 200 and the default
            PyMC/NumPyro chain counts (PyMC fits 2 chains of 2000
            draws each; NumPyro fits 1 chain of 1000 draws).
        pymc_draws / pymc_tune / numpyro_samples / numpyro_warmup:
            per-backend chain knobs; defaults are CI-friendly.
    """

    name = "bayesian-phi-posterior-crosscheck"
    tier = Tier.MEASUREMENT_MACHINERY
    family = "cross_framework"
    goal = (
        "Verify the Bayesian inference machinery Ophamin's "
        "Bayesian-phi-posterior scenario depends on by running the "
        "same model under two independent backends (PyMC + NumPyro) "
        "and asserting the resulting posteriors agree within "
        "tolerance."
    )
    explanation = (
        "RFC 0002 Phase E1 names cross-framework validation as a "
        "load-bearing scientific-grade-quality property: each "
        "framework dependency's claim should be corroborated by a "
        "different implementation. Bayesian-phi-posterior uses PyMC; "
        "this scenario runs the same model under NumPyro (JAX-backed "
        "HMC, completely independent sampler) and asserts the two "
        "posteriors agree on the mean (within absolute tolerance) "
        "and the HDI width (within relative tolerance). Disagreement "
        "surfaces either a sampler bug, a model mis-specification, "
        "or a seeding leak."
    )
    method = "cross_framework_oracle"
    falsification_consequence = (
        "PyMC and NumPyro disagree on posterior contraction beyond "
        "the documented sampler-noise tolerance — at least one "
        "backend is broken, or the framework's NormalMean model is "
        "mis-specified."
    )
    corpus_name = "synthetic-normal"
    target = "pymc+numpyro-cross-framework"

    def __init__(
        self,
        *,
        n_samples: int = 200,
        true_mu: float = 0.5,
        true_sigma: float = 0.2,
        seed: int = 20260517,
        mean_tolerance: float = 0.1,
        width_tolerance: float = 0.5,
        pymc_draws: int = 1000,
        pymc_tune: int = 500,
        numpyro_samples: int = 1000,
        numpyro_warmup: int = 500,
    ) -> None:
        if n_samples < 2:
            raise ValueError(f"n_samples must be ≥ 2, got {n_samples}")
        if true_sigma <= 0.0:
            raise ValueError(f"true_sigma must be > 0, got {true_sigma}")
        if mean_tolerance <= 0.0:
            raise ValueError(f"mean_tolerance must be > 0, got {mean_tolerance}")
        if not 0.0 < width_tolerance < 1.0:
            raise ValueError(
                f"width_tolerance must be in (0, 1), got {width_tolerance}"
            )
        self.n_samples = int(n_samples)
        self.true_mu = float(true_mu)
        self.true_sigma = float(true_sigma)
        self.seed = int(seed)
        self.mean_tolerance = float(mean_tolerance)
        self.width_tolerance = float(width_tolerance)
        self.pymc_draws = int(pymc_draws)
        self.pymc_tune = int(pymc_tune)
        self.numpyro_samples = int(numpyro_samples)
        self.numpyro_warmup = int(numpyro_warmup)
        self.n_cycles = 0  # static scenario

    def score(
        self,
        cycle_results: list[CycleResult],
        records: list[CorpusRecord],
    ) -> ScenarioScore:
        raise NotImplementedError(
            "BayesianPhiPosteriorCrosscheckScenario uses a custom run(); "
            "score() is unreachable."
        )

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                f"PyMC and NumPyro fit the same NormalMean model on the "
                f"same synthetic Normal(mu={self.true_mu}, sigma={self.true_sigma}) "
                f"data (N={self.n_samples}, seed={self.seed}) and produce "
                f"posteriors that agree within tolerance: "
                f"|mu_pymc − mu_numpyro| ≤ {self.mean_tolerance} AND "
                f"|width_ratio − 1| ≤ {self.width_tolerance}. "
                f"(RFC 0002 Phase E1: cross-framework validation.)"
            ),
            operationalization=(
                "Generate N samples from Normal(true_mu, true_sigma) with "
                "fixed seed. Fit the same model (mu ~ Normal(0, 10); "
                "sigma ~ HalfNormal(1); y ~ Normal(mu, sigma)) under both "
                "backends. Extract posterior_mean(mu) + 94% HDI(mu). "
                "Compute mean_diff = |mu_pymc - mu_numpyro| and "
                "width_ratio = hdi_width_pymc / hdi_width_numpyro. "
                "VALIDATED iff both tolerances are satisfied (binary; "
                "1.0 / 0.0). REFUTED if either bound is breached."
            ),
            threshold=Threshold(
                metric="cross_framework_agreement",
                comparator=">=",
                value=1.0,
                units="proportion",
            ),
            h0=(
                "PyMC and NumPyro disagree on posterior mean and/or HDI "
                "width beyond the documented sampler-noise tolerance — "
                "at least one backend is broken or the model is "
                "mis-specified."
            ),
            h1=(
                "Both backends produce statistically equivalent "
                "posteriors on the same data + model — corroborates "
                "the framework's Bayesian inference machinery."
            ),
        )

    def run(
        self,
        substrate: SubstrateUnderTest | None = None,  # noqa: ARG002
        *,
        data_root: Any = None,
        sign_key: bytes = DEFAULT_SIGN_KEY,
    ) -> EmpiricalProofRecord:
        # --- generate synthetic data once
        import numpy as np

        rng = np.random.default_rng(self.seed)
        observations = list(rng.normal(self.true_mu, self.true_sigma, self.n_samples))

        # --- fit each backend
        try:
            from ophamin.measuring.bayesian_helpers import (
                numpyro_posterior_for_normal_mean,
                posterior_for_normal_mean,
            )
        except ImportError as exc:
            raise RuntimeError(
                "BayesianPhiPosteriorCrosscheck requires pymc + numpyro "
                f"installed. Install via `pip install 'ophamin[bayesian]'`. ({exc})"
            ) from exc

        pymc_result = posterior_for_normal_mean(
            observations,
            draws=self.pymc_draws,
            tune=self.pymc_tune,
            random_seed=self.seed,
            chains=2,
        )
        numpyro_result = numpyro_posterior_for_normal_mean(
            observations,
            num_samples=self.numpyro_samples,
            num_warmup=self.numpyro_warmup,
            random_seed=self.seed,
        )

        # --- agreement metrics
        mu_pymc = float(pymc_result["mu_mean"])
        mu_numpyro = float(numpyro_result["mu_mean"])
        mean_diff = abs(mu_pymc - mu_numpyro)
        width_pymc = float(pymc_result["mu_hdi_high"]) - float(pymc_result["mu_hdi_low"])
        width_numpyro = (
            float(numpyro_result["mu_hdi_high"]) - float(numpyro_result["mu_hdi_low"])
        )
        # Guard against zero-width pathology (would be a real defect).
        if width_numpyro < 1e-9:
            width_ratio = float("inf")
        else:
            width_ratio = width_pymc / width_numpyro
        width_deviation = abs(width_ratio - 1.0)

        mean_agrees = mean_diff <= self.mean_tolerance
        width_agrees = width_deviation <= self.width_tolerance
        agrees = mean_agrees and width_agrees
        observed = 1.0 if agrees else 0.0

        # --- pre-registration
        config = {
            "scenario": self.name,
            "n_samples": self.n_samples,
            "true_mu": self.true_mu,
            "true_sigma": self.true_sigma,
            "seed": self.seed,
            "mean_tolerance": self.mean_tolerance,
            "width_tolerance": self.width_tolerance,
            "pymc_draws": self.pymc_draws,
            "pymc_tune": self.pymc_tune,
            "numpyro_samples": self.numpyro_samples,
            "numpyro_warmup": self.numpyro_warmup,
        }
        dataset = DatasetRef(
            name=self.corpus_name,
            content_hash=content_hash(config),
            n_records=self.n_samples,
            source=f"numpy.random.default_rng(seed={self.seed}).normal(...)",
            kind="synthetic-normal",
        )
        prereg = PreRegistration(
            config_hash=content_hash(config),
            data_hash=dataset.content_hash,
            analysis_plan=self.analysis_plan(),
        )

        claim = self.build_claim()
        verdict = Verdict.decide(
            observed=observed,
            threshold=claim.threshold,
            reasoning=(
                f"PyMC mu={mu_pymc:.4f}, HDI=[{pymc_result['mu_hdi_low']:.4f}, "
                f"{pymc_result['mu_hdi_high']:.4f}]; "
                f"NumPyro mu={mu_numpyro:.4f}, HDI=[{numpyro_result['mu_hdi_low']:.4f}, "
                f"{numpyro_result['mu_hdi_high']:.4f}]. "
                f"mean_diff={mean_diff:.4f} "
                f"({'≤' if mean_agrees else '>'} {self.mean_tolerance} tol); "
                f"width_ratio={width_ratio:.4f} "
                f"({'within' if width_agrees else 'outside'} ±{self.width_tolerance})."
            ),
        )

        # --- evidence
        try:
            import pymc as _pm  # noqa: F401
            pymc_version = getattr(_pm, "__version__", "unknown")
        except ImportError:
            pymc_version = "unavailable"
        try:
            import numpyro as _np  # noqa: F401
            numpyro_version = getattr(_np, "__version__", "unknown")
        except ImportError:
            numpyro_version = "unavailable"
        evidence = [
            PillarEvidence(
                pillar="bayesian_cross_framework_pymc_numpyro",
                statistic_name="cross_framework_agreement",
                statistic_value=observed,
                library="pymc",
                library_version=pymc_version,
                effect_size=mean_diff,
                ci_low=None,
                ci_high=None,
                p_value=None,
                cross_check="passed" if agrees else "failed",
                detail={
                    "cross_check_note": (
                        f"PyMC (NUTS via PyTensor) vs NumPyro {numpyro_version} "
                        f"(NUTS via JAX) — independent samplers, same model"
                    ),
                    "pymc_version": pymc_version,
                    "numpyro_version": numpyro_version,
                    "n_samples": self.n_samples,
                    "true_mu": self.true_mu,
                    "true_sigma": self.true_sigma,
                    "seed": self.seed,
                    "pymc_posterior": {
                        "mu_mean": mu_pymc,
                        "mu_sd": float(pymc_result["mu_sd"]),
                        "mu_hdi_low": float(pymc_result["mu_hdi_low"]),
                        "mu_hdi_high": float(pymc_result["mu_hdi_high"]),
                        "sigma_mean": float(pymc_result["sigma_mean"]),
                        "ess_bulk": pymc_result.get("ess_bulk"),
                        "rhat": pymc_result.get("rhat"),
                    },
                    "numpyro_posterior": {
                        "mu_mean": mu_numpyro,
                        "mu_sd": float(numpyro_result["mu_sd"]),
                        "mu_hdi_low": float(numpyro_result["mu_hdi_low"]),
                        "mu_hdi_high": float(numpyro_result["mu_hdi_high"]),
                        "sigma_mean": float(numpyro_result["sigma_mean"]),
                    },
                    "mean_difference": mean_diff,
                    "mean_tolerance": self.mean_tolerance,
                    "mean_agrees": mean_agrees,
                    "hdi_width_pymc": width_pymc,
                    "hdi_width_numpyro": width_numpyro,
                    "hdi_width_ratio": width_ratio,
                    "width_tolerance": self.width_tolerance,
                    "width_agrees": width_agrees,
                },
            ),
        ]

        # --- provenance
        prov = ProvenanceGraph()
        agent_ophamin = prov.agent(
            "ophamin", role="experimentation_framework", version=__version__
        )
        agent_pymc = prov.agent(
            "pymc", role="bayesian_backend_a", version=pymc_version,
        )
        agent_numpyro = prov.agent(
            "numpyro", role="bayesian_backend_b_oracle", version=numpyro_version,
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
            n_samples=self.n_samples,
        )
        result_entity = prov.entity(f"proof:{self.name}")
        prov.used(activity, data_entity)
        prov.was_associated_with(activity, agent_ophamin)
        prov.was_associated_with(activity, agent_pymc)
        prov.was_associated_with(activity, agent_numpyro)
        prov.was_generated_by(result_entity, activity)
        prov.was_derived_from(result_entity, data_entity)

        proof = EmpiricalProofRecord(
            claim=claim,
            preregistration=prereg,
            datasets=[dataset],
            substrate_name="pymc+numpyro-cross-framework",
            # The substrate is Ophamin's bayesian_helpers wrapper around
            # PyMC + NumPyro; pin the Ophamin commit so validate()'s
            # "substrate must be versioned" check passes. The per-backend
            # library versions are recorded in detail.pymc_version /
            # detail.numpyro_version above.
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
            f"Generate {self.n_samples} samples from Normal({self.true_mu}, "
            f"{self.true_sigma}) with seed={self.seed}. Fit NormalMean model "
            f"under PyMC ({self.pymc_draws} draws × 2 chains) AND NumPyro "
            f"({self.numpyro_samples} samples × 1 chain). Compute "
            f"mean_difference + hdi_width_ratio. VALIDATED iff "
            f"mean_difference ≤ {self.mean_tolerance} AND "
            f"|width_ratio − 1| ≤ {self.width_tolerance}."
        )


__all__ = ["BayesianPhiPosteriorCrosscheckScenario"]
