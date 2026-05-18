"""The Bayesian Φ-Posterior scenario — posterior tightens with more observations.

Per CLAUDE.md Family L EV-71: Kimera's IIT-derived Φ values across 200
genesis-axiom cycles produced mean **0.621 ± 0.065** (range 0.457–0.798).
The Bayesian-tier scenario tests whether classical Bayesian-inference
machinery — PyMC NUTS posterior sampling — recovers the *correct* posterior
behaviour when applied to real Kimera Φ trajectories.

Falsifiable claim
=================

> The posterior 94% HDI width on μ_Φ contracts at the theoretical √N rate
> as the number of observations grows. Specifically:
>
>     HDI_width(N=200) / HDI_width(N=20) ≤ 0.40
>
> The theoretical contraction factor is √(20/200) = √0.1 ≈ 0.316; the 0.40
> ceiling allows ~25% slack for finite-sample noise.

If the contraction ratio EXCEEDS 0.40, either (a) the data is non-Gaussian
in a way the Normal-mean prior can't accommodate, (b) the Φ trajectory is
non-stationary (drift across the run), or (c) PyMC's NUTS sampler is mis-
calibrated. All three are findings worth investigating; the scenario
distinguishes them via the per-sample-size posterior summaries it ships in
the proof record.

Inputs
======

The scenario takes either:

* ``phi_trajectory_path`` — JSON file containing a ``phi_values`` list, OR
* ``phi_values`` — direct list of Φ samples, OR
* ``simulate_from_family_l`` (default True) — generate samples from
  Normal(0.621, 0.065) per Family L EV-71 and run the scenario as a
  *self-test* of the posterior machinery (used for development + CI).

Output
======

A signed ``EmpiricalProofRecord`` carrying:

* the contraction ratio observed
* per-sample-size posterior summary (mean, sd, HDI low/high, ESS, R-hat)
* the Φ trajectory's empirical mean / sd
* the data source (real trajectory path or "simulated_from_family_l")

This scenario is the cleanest demo of the round-3 ``bayesian_helpers``
module driving a real Ophamin scenario claim.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any

from ophamin import __version__
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
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, Scenario, ScenarioScore, Tier
from ophamin.seeing.corpus import CorpusRecord
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest


# Sample sizes at which to fit the posterior. The ratio HDI(largest) /
# HDI(smallest) is the contraction metric.
DEFAULT_SAMPLE_SIZES: tuple[int, ...] = (20, 50, 100, 200)

# Family L EV-71 reference values (CLAUDE.md, 2026-05-12).
FAMILY_L_PHI_MEAN: float = 0.621
FAMILY_L_PHI_SD: float = 0.065


class BayesianPhiPosteriorScenario(Scenario):
    """Bayesian posterior contraction on Kimera Φ samples."""

    name = "bayesian-phi-posterior"
    tier = Tier.EMPIRICAL_DEEP
    family = "phi"
    goal = (
        "Validate that classical Bayesian-inference machinery (PyMC "
        "NUTS) recovers correct posterior contraction on real "
        "Kimera Phi trajectories."
    )
    explanation = (
        "Kimera's IIT-derived Phi values across 200 genesis-axiom "
        "cycles produced mean 0.621 +/- 0.065 (Family L EV-71). "
        "The Bayesian-tier scenario tests posterior contraction at "
        "the theoretical sqrt(N) rate: HDI_width(N=200) / "
        "HDI_width(N=20) should be <= 0.40 (theoretical 0.316, "
        "with ~25% slack for finite-sample noise). A failure may "
        "indicate non-Gaussian data, non-stationary Phi "
        "trajectory, or mis-calibrated NUTS sampler — the "
        "per-sample-size posterior summaries distinguish them."
    )
    method = "bayesian_posterior_contraction"
    falsification_consequence = (
        "Posterior HDI fails to contract at sqrt(N) rate — either "
        "the data is non-Gaussian, the Phi trajectory is "
        "non-stationary, or PyMC NUTS is mis-calibrated for this "
        "regime."
    )
    corpus_name = "kimera-phi-trajectory"
    target = "phi_values_via_pymc_posterior"

    def __init__(
        self,
        *,
        phi_values: list[float] | tuple[float, ...] | None = None,
        phi_trajectory_path: str | Path | None = None,
        simulate_from_family_l: bool = True,
        sample_sizes: tuple[int, ...] = DEFAULT_SAMPLE_SIZES,
        contraction_ceiling: float = 0.40,
        prior_mean: float = 0.5,
        prior_sd: float = 1.0,
        draws: int = 1000,
        tune: int = 500,
        chains: int = 2,
        seed: int = 20260515,
    ) -> None:
        if not sample_sizes or len(sample_sizes) < 2:
            raise ValueError(
                f"sample_sizes must have ≥ 2 entries, got {sample_sizes}"
            )
        if any(n < 2 for n in sample_sizes):
            raise ValueError(f"every sample_size must be ≥ 2, got {sample_sizes}")
        if not 0.0 < contraction_ceiling < 1.0:
            raise ValueError(
                f"contraction_ceiling must be in (0, 1), got {contraction_ceiling}"
            )
        # exactly one of (phi_values, phi_trajectory_path, simulate_from_family_l) wins
        sources = [phi_values is not None, phi_trajectory_path is not None,
                   simulate_from_family_l]
        if sum(sources) != 1:
            raise ValueError(
                "exactly one of phi_values, phi_trajectory_path, "
                f"simulate_from_family_l must be set; got {sources}"
            )
        self.phi_values = list(phi_values) if phi_values is not None else None
        self.phi_trajectory_path = (
            Path(phi_trajectory_path).expanduser() if phi_trajectory_path else None
        )
        self.simulate_from_family_l = bool(simulate_from_family_l)
        self.sample_sizes = tuple(sorted(set(int(n) for n in sample_sizes)))
        self.contraction_ceiling = float(contraction_ceiling)
        self.prior_mean = float(prior_mean)
        self.prior_sd = float(prior_sd)
        self.draws = int(draws)
        self.tune = int(tune)
        self.chains = int(chains)
        self.seed = int(seed)
        self.n_cycles = 0  # static scenario — base.run() is overridden

    def score(
        self,
        cycle_results: list[CycleResult],
        records: list[CorpusRecord],
    ) -> ScenarioScore:
        raise NotImplementedError(
            "BayesianPhiPosteriorScenario uses a custom run() loop; "
            "score() is unreachable."
        )

    def build_claim(self) -> Claim:
        smallest = self.sample_sizes[0]
        largest = self.sample_sizes[-1]
        theoretical = math.sqrt(smallest / largest)
        return Claim(
            statement=(
                f"The posterior 94% HDI width on μ_Φ contracts at the "
                f"theoretical √N rate as the number of observations grows. "
                f"Specifically, HDI_width(N={largest}) / HDI_width(N={smallest}) "
                f"≤ {self.contraction_ceiling:.2f} (theoretical contraction "
                f"factor √({smallest}/{largest}) = {theoretical:.3f}; "
                f"the {self.contraction_ceiling:.2f} ceiling allows finite-"
                "sample slack)."
            ),
            operationalization=(
                "Fit a PyMC NUTS posterior to subsamples of the Φ trajectory "
                "at sizes "
                + ", ".join(str(n) for n in self.sample_sizes)
                + ". Posterior model: μ ~ Normal(prior), σ ~ HalfNormal, "
                "y_i ~ Normal(μ, σ). Compute the 94% HDI width on μ at each "
                "size; the contraction metric is "
                f"HDI_width(N={largest}) / HDI_width(N={smallest})."
            ),
            threshold=Threshold(
                metric="hdi_contraction_ratio",
                comparator="<=",
                value=self.contraction_ceiling,
                units="ratio",
            ),
            h0=(
                f"hdi_contraction_ratio > {self.contraction_ceiling:.2f} "
                "(posterior fails to tighten at the predicted rate — data "
                "may be non-Gaussian, non-stationary, or sampler "
                "mis-calibrated)"
            ),
            h1=(
                f"hdi_contraction_ratio <= {self.contraction_ceiling:.2f} "
                "(posterior tightens approximately at the theoretical √N "
                "rate, confirming Bayesian inference behaves correctly on "
                "the Φ trajectory)"
            ),
        )

    # ------------------------------------------------------------------ run --

    def _load_phi_values(self) -> tuple[list[float], str]:
        """Returns (samples, source_label)."""
        if self.phi_values is not None:
            return list(self.phi_values), "user_supplied_list"
        if self.phi_trajectory_path is not None:
            data = json.loads(self.phi_trajectory_path.read_text())
            values = data["phi_values"] if isinstance(data, dict) else data
            return [float(v) for v in values], f"json:{self.phi_trajectory_path}"
        # simulate_from_family_l
        rng = random.Random(self.seed)
        n_needed = max(self.sample_sizes)
        return (
            [rng.gauss(FAMILY_L_PHI_MEAN, FAMILY_L_PHI_SD) for _ in range(n_needed)],
            f"simulated_normal({FAMILY_L_PHI_MEAN}, {FAMILY_L_PHI_SD})_seed={self.seed}",
        )

    def run(
        self,
        substrate: SubstrateUnderTest | None = None,
        *,
        data_root: Any = None,
        sign_key: bytes = DEFAULT_SIGN_KEY,
    ) -> EmpiricalProofRecord:
        try:
            from ophamin.measuring.bayesian_helpers import posterior_for_normal_mean
        except ImportError as e:
            raise RuntimeError(
                "BayesianPhiPosteriorScenario requires pymc + arviz installed. "
                f"Install via `pip install 'ophamin[bayesian]'`. ({e})"
            ) from e

        phi_samples, source_label = self._load_phi_values()
        if max(self.sample_sizes) > len(phi_samples):
            raise ValueError(
                f"largest sample_size ({max(self.sample_sizes)}) exceeds "
                f"available Φ samples ({len(phi_samples)})"
            )

        # Empirical sanity stats on the raw samples
        n_total = len(phi_samples)
        emp_mean = sum(phi_samples) / n_total
        emp_var = sum((x - emp_mean) ** 2 for x in phi_samples) / max(n_total - 1, 1)
        emp_sd = math.sqrt(emp_var)

        # Fit posterior at each sample size; capture HDI widths
        per_size: list[dict[str, Any]] = []
        for n in self.sample_sizes:
            subsample = phi_samples[:n]
            try:
                posterior = posterior_for_normal_mean(
                    subsample,
                    prior_mean=self.prior_mean,
                    prior_sd=self.prior_sd,
                    draws=self.draws,
                    tune=self.tune,
                    chains=self.chains,
                    random_seed=self.seed,
                )
            except Exception as e:
                # Surface failure into the proof record without lying about success
                per_size.append({
                    "n": n,
                    "error": f"{type(e).__name__}: {e}",
                })
                continue
            per_size.append({
                "n": n,
                "mu_mean": posterior["mu_mean"],
                "mu_sd": posterior["mu_sd"],
                "hdi_low": posterior["mu_hdi_low"],
                "hdi_high": posterior["mu_hdi_high"],
                "hdi_width": posterior["mu_hdi_high"] - posterior["mu_hdi_low"],
                "sigma_mean": posterior["sigma_mean"],
                "ess_bulk": posterior.get("ess_bulk", 0.0),
                "rhat": posterior.get("rhat", 0.0),
            })

        # Compute contraction ratio
        first = next((row for row in per_size if "hdi_width" in row), None)
        last = next((row for row in reversed(per_size) if "hdi_width" in row), None)
        if first is None or last is None or first is last:
            raise RuntimeError(
                "BayesianPhiPosteriorScenario could not compute contraction "
                "ratio — at least 2 sample sizes must produce HDI widths"
            )
        # Guard against zero-width HDI (happens when the input data is so
        # tightly concentrated that the posterior σ collapses to numerical
        # zero — measurement-design issue, not substrate property).
        _ZERO_HDI_EPS = 1e-9
        if first["hdi_width"] < _ZERO_HDI_EPS:
            inconclusive = True
            observed = 0.0
            inconclusive_reason = (
                f"HDI width at smallest N (={first['n']}) is "
                f"{first['hdi_width']:.6e} — below epsilon {_ZERO_HDI_EPS}. "
                "Input data is too tightly concentrated for posterior contraction "
                "to be meaningfully measured. Provide higher-variance Φ samples."
            )
        else:
            inconclusive = False
            observed = last["hdi_width"] / first["hdi_width"]
            inconclusive_reason = ""
        theoretical = math.sqrt(first["n"] / last["n"])

        # PRE-REGISTRATION
        config = {
            "scenario": self.name,
            "sample_sizes": list(self.sample_sizes),
            "contraction_ceiling": self.contraction_ceiling,
            "prior_mean": self.prior_mean,
            "prior_sd": self.prior_sd,
            "draws": self.draws,
            "tune": self.tune,
            "chains": self.chains,
            "seed": self.seed,
            "source_label": source_label,
        }
        dataset = DatasetRef(
            name=self.corpus_name,
            content_hash=content_hash({
                "phi_samples_first_5": phi_samples[:5],
                "phi_samples_last_5": phi_samples[-5:],
                "n_total": n_total,
            }),
            n_records=n_total,
            source=source_label,
            kind="phi-value-trajectory",
        )
        prereg = PreRegistration(
            config_hash=content_hash(config),
            data_hash=dataset.content_hash,
            analysis_plan=self.analysis_plan(),
        )

        claim = self.build_claim()
        if inconclusive:
            verdict = Verdict.decide(
                observed=observed,
                threshold=claim.threshold,
                reasoning=inconclusive_reason,
                inconclusive=True,
            )
        else:
            verdict = Verdict.decide(
                observed=observed,
                threshold=claim.threshold,
                reasoning=(
                    f"HDI width N={first['n']} → N={last['n']}: "
                    f"{first['hdi_width']:.4f} → {last['hdi_width']:.4f}; "
                    f"contraction ratio {observed:.4f} (theoretical "
                    f"{theoretical:.4f}; ceiling {self.contraction_ceiling:.4f}). "
                    f"Empirical Φ mean={emp_mean:.4f} sd={emp_sd:.4f} (n={n_total})."
                ),
            )

        try:
            import pymc as _pm
            pymc_version = getattr(_pm, "__version__", "unknown")
        except ImportError:
            pymc_version = "unavailable"

        evidence = [
            PillarEvidence(
                pillar="pymc_nuts_posterior",
                statistic_name="hdi_contraction_ratio",
                statistic_value=observed,
                library="pymc",
                library_version=pymc_version,
                effect_size=None,
                ci_low=None,
                ci_high=None,
                p_value=None,
                # Cross-check against the theoretical √N lower bound:
                # the observed HDI contraction should be ≥ the lower bound
                # if the Bayesian inference is converging properly.
                cross_check="passed" if observed >= theoretical else "failed",
                detail={
                    "cross_check_note": (
                        "theoretical √N contraction = "
                        f"{theoretical:.4f} (lower bound under iid Normal samples)"
                    ),
                    "phi_source": source_label,
                    "n_phi_samples_total": n_total,
                    "phi_empirical_mean": emp_mean,
                    "phi_empirical_sd": emp_sd,
                    "sample_sizes": list(self.sample_sizes),
                    "per_size_posterior": per_size,
                    "theoretical_contraction": theoretical,
                    "contraction_ceiling": self.contraction_ceiling,
                    "smallest_n_hdi_width": first["hdi_width"],
                    "largest_n_hdi_width": last["hdi_width"],
                    "smallest_n": first["n"],
                    "largest_n": last["n"],
                },
            ),
        ]

        # PROVENANCE
        prov = ProvenanceGraph()
        agent_ophamin = prov.agent(
            "ophamin", role="experimentation_framework", version=__version__
        )
        agent_pymc = prov.agent(
            "pymc", role="bayesian_inference_engine", version=pymc_version
        )
        data_entity = prov.entity(
            f"corpus:{dataset.name}",
            content_hash=dataset.content_hash,
            n_records=dataset.n_records,
            kind=dataset.kind,
            source=source_label,
        )
        activity = prov.activity(
            f"scenario:{self.name}",
            target=self.target,
            n_phi_samples=n_total,
            sample_sizes=str(list(self.sample_sizes)),
        )
        result_entity = prov.entity(f"proof:{self.name}")
        prov.used(activity, data_entity)
        prov.was_associated_with(activity, agent_ophamin)
        prov.was_associated_with(activity, agent_pymc)
        prov.was_generated_by(result_entity, activity)
        prov.was_derived_from(result_entity, data_entity)

        proof = EmpiricalProofRecord(
            claim=claim,
            preregistration=prereg,
            datasets=[dataset],
            substrate_name="phi_trajectory+pymc",
            substrate_git_commit="",  # not git-tracked; data + library check
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
            f"Fit a PyMC NUTS posterior on the Φ trajectory at sample sizes "
            + ", ".join(str(n) for n in self.sample_sizes)
            + f". Compute 94% HDI width on μ at each size; verdict against "
            f"hdi_contraction_ratio = HDI_width(N={self.sample_sizes[-1]}) / "
            f"HDI_width(N={self.sample_sizes[0]}) ≤ {self.contraction_ceiling:.2f}."
        )
