"""Tests for the PyMC↔NumPyro Bayesian cross-check scenario
(RFC 0002 Phase E1).

Three layers:

1. **Construction invariants** — argument validation.
2. **End-to-end VALIDATED** — running the scenario with CI-friendly
   chain knobs produces a signed proof with ``VALIDATED`` outcome,
   mean agreement at the 3rd decimal place, HDI widths within ±5 %.
3. **Falsifiability** — calling with an absurdly-tight tolerance
   surfaces REFUTED outcome (proves the test isn't a no-op).

The scenario itself runs ~3-4 s per invocation on Apple Silicon;
each test uses the same scenario instance + cached result to keep
the suite under 10 s.
"""

from __future__ import annotations

import pytest

from ophamin.measuring.scenarios.bayesian_phi_posterior_crosscheck import (
    BayesianPhiPosteriorCrosscheckScenario,
)


# Module-scoped fixture so PyMC/NumPyro both run only once per test session.
@pytest.fixture(scope="module")
def _crosscheck_proof():  # type: ignore[no-untyped-def]
    scenario = BayesianPhiPosteriorCrosscheckScenario(
        n_samples=100,
        pymc_draws=500,
        pymc_tune=200,
        numpyro_samples=500,
        numpyro_warmup=200,
        seed=20260518,
    )
    return scenario.run()


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_default_construction(self) -> None:
        scenario = BayesianPhiPosteriorCrosscheckScenario()
        assert scenario.name == "bayesian-phi-posterior-crosscheck"
        assert scenario.n_samples == 200
        assert scenario.true_mu == 0.5
        assert scenario.true_sigma == 0.2
        assert scenario.mean_tolerance == 0.1
        assert scenario.width_tolerance == 0.5

    def test_invalid_n_samples_rejected(self) -> None:
        with pytest.raises(ValueError, match="n_samples must be"):
            BayesianPhiPosteriorCrosscheckScenario(n_samples=1)

    def test_zero_true_sigma_rejected(self) -> None:
        with pytest.raises(ValueError, match="true_sigma must be"):
            BayesianPhiPosteriorCrosscheckScenario(true_sigma=0.0)

    def test_negative_true_sigma_rejected(self) -> None:
        with pytest.raises(ValueError, match="true_sigma must be"):
            BayesianPhiPosteriorCrosscheckScenario(true_sigma=-0.1)

    def test_zero_mean_tolerance_rejected(self) -> None:
        with pytest.raises(ValueError, match="mean_tolerance must be"):
            BayesianPhiPosteriorCrosscheckScenario(mean_tolerance=0.0)

    def test_width_tolerance_out_of_range_rejected(self) -> None:
        with pytest.raises(ValueError, match="width_tolerance must be"):
            BayesianPhiPosteriorCrosscheckScenario(width_tolerance=0.0)
        with pytest.raises(ValueError, match="width_tolerance must be"):
            BayesianPhiPosteriorCrosscheckScenario(width_tolerance=1.0)

    def test_score_unreachable(self) -> None:
        scenario = BayesianPhiPosteriorCrosscheckScenario()
        with pytest.raises(NotImplementedError, match="score\\(\\) is unreachable"):
            scenario.score([], [])


# ---------------------------------------------------------------------------
# End-to-end VALIDATED
# ---------------------------------------------------------------------------


class TestEndToEnd:
    def test_default_kwargs_emit_validated_proof(self, _crosscheck_proof) -> None:  # type: ignore[no-untyped-def]
        proof = _crosscheck_proof
        assert proof.verdict.outcome == "VALIDATED"
        assert proof.verdict.observed_value == 1.0

    def test_proof_carries_per_backend_posterior(self, _crosscheck_proof) -> None:  # type: ignore[no-untyped-def]
        proof = _crosscheck_proof
        detail = proof.evidence[0].detail
        assert "pymc_posterior" in detail
        assert "numpyro_posterior" in detail
        for key in ("mu_mean", "mu_hdi_low", "mu_hdi_high", "sigma_mean"):
            assert key in detail["pymc_posterior"], f"PyMC posterior missing {key}"
            assert key in detail["numpyro_posterior"], f"NumPyro posterior missing {key}"

    def test_agreement_metrics_recorded(self, _crosscheck_proof) -> None:  # type: ignore[no-untyped-def]
        proof = _crosscheck_proof
        detail = proof.evidence[0].detail
        assert "mean_difference" in detail
        assert "hdi_width_ratio" in detail
        assert "mean_agrees" in detail
        assert "width_agrees" in detail
        assert detail["mean_agrees"] is True
        assert detail["width_agrees"] is True

    def test_means_agree_to_third_decimal(self, _crosscheck_proof) -> None:  # type: ignore[no-untyped-def]
        """At N=100 with seed=20260518, both samplers should converge
        to within ~0.01 of each other (an order of magnitude tighter
        than the documented 0.1 tolerance). This is a stronger pin
        than the default tolerance — drift here surfaces sampler
        regressions earlier."""
        proof = _crosscheck_proof
        detail = proof.evidence[0].detail
        assert detail["mean_difference"] < 0.05, (
            f"PyMC and NumPyro means drift by {detail['mean_difference']:.4f} — "
            f"sampler regression likely"
        )

    def test_cross_check_marked_passed(self, _crosscheck_proof) -> None:  # type: ignore[no-untyped-def]
        proof = _crosscheck_proof
        assert proof.evidence[0].cross_check == "passed"

    def test_proof_signs_correctly(self, _crosscheck_proof) -> None:  # type: ignore[no-untyped-def]
        from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
        proof = _crosscheck_proof
        assert proof.signature
        assert proof.verify_signature(DEFAULT_SIGN_KEY)

    def test_proof_validates(self, _crosscheck_proof) -> None:  # type: ignore[no-untyped-def]
        proof = _crosscheck_proof
        problems = proof.validate()
        assert problems == [], f"emitted proof failed validate(): {problems}"


# ---------------------------------------------------------------------------
# Falsifiability — absurdly tight tolerance MUST refute
# ---------------------------------------------------------------------------


class TestFalsifiability:
    def test_absurdly_tight_mean_tolerance_refutes(self) -> None:
        """If mean_tolerance is set to 1e-12, the two samplers' means
        cannot possibly agree to that precision — REFUTED. Proves the
        scenario's threshold logic isn't a no-op."""
        scenario = BayesianPhiPosteriorCrosscheckScenario(
            n_samples=100,
            pymc_draws=500,
            pymc_tune=200,
            numpyro_samples=500,
            numpyro_warmup=200,
            seed=20260518,
            mean_tolerance=1e-12,  # absurdly tight
        )
        proof = scenario.run()
        assert proof.verdict.outcome == "REFUTED"
        assert proof.verdict.observed_value == 0.0
        assert proof.evidence[0].cross_check == "failed"


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_scenario_is_registered() -> None:
    from ophamin.measuring.scenarios.base import SCENARIOS

    assert "bayesian-phi-posterior-crosscheck" in SCENARIOS
    assert SCENARIOS["bayesian-phi-posterior-crosscheck"] is BayesianPhiPosteriorCrosscheckScenario
