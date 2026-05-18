"""Tests for WilsonCICrosscheckScenario (RFC 0002 Phase E1.2)."""

from __future__ import annotations

import pytest

from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
from ophamin.measuring.scenarios.wilson_ci_crosscheck import (
    WilsonCICrosscheckScenario,
)


class TestConstruction:
    def test_default(self) -> None:
        s = WilsonCICrosscheckScenario()
        assert s.name == "wilson-ci-crosscheck"
        assert s.n_pairs == 100
        assert s.confidence == 0.95
        assert s.tolerance == 1e-9

    def test_invalid_n_pairs(self) -> None:
        with pytest.raises(ValueError, match="n_pairs must be"):
            WilsonCICrosscheckScenario(n_pairs=0)

    def test_invalid_max_n(self) -> None:
        with pytest.raises(ValueError, match="max_n must be"):
            WilsonCICrosscheckScenario(max_n=1)

    def test_invalid_tolerance(self) -> None:
        with pytest.raises(ValueError, match="tolerance must be"):
            WilsonCICrosscheckScenario(tolerance=0.0)

    def test_invalid_confidence(self) -> None:
        with pytest.raises(ValueError, match="confidence must be"):
            WilsonCICrosscheckScenario(confidence=1.0)
        with pytest.raises(ValueError, match="confidence must be"):
            WilsonCICrosscheckScenario(confidence=0.0)

    def test_score_unreachable(self) -> None:
        s = WilsonCICrosscheckScenario()
        with pytest.raises(NotImplementedError):
            s.score([], [])


class TestEndToEnd:
    def test_small_run_validates(self) -> None:
        s = WilsonCICrosscheckScenario(n_pairs=20)
        proof = s.run()
        assert proof.verdict.outcome == "VALIDATED"
        assert proof.evidence[0].cross_check == "passed"

    def test_machine_epsilon_agreement(self) -> None:
        """scipy and statsmodels must agree at float64 precision."""
        s = WilsonCICrosscheckScenario(n_pairs=20)
        proof = s.run()
        # Empirically: max diff ~ 1e-16 (machine epsilon for float64).
        # Pin a tighter bound than the default 1e-9 tolerance.
        assert proof.evidence[0].statistic_value < 1e-12, (
            f"scipy and statsmodels disagree on Wilson CI by "
            f"{proof.evidence[0].statistic_value:.3e} — sampler regression?"
        )

    def test_signed_proof(self) -> None:
        s = WilsonCICrosscheckScenario(n_pairs=20)
        proof = s.run()
        assert proof.signature
        assert proof.verify_signature(DEFAULT_SIGN_KEY)
        assert proof.validate() == []

    def test_falsifiability_absurd_tolerance(self) -> None:
        """A 1e-100 tolerance MUST refute (machine epsilon is 1e-16)."""
        s = WilsonCICrosscheckScenario(n_pairs=20, tolerance=1e-100)
        proof = s.run()
        assert proof.verdict.outcome == "REFUTED"
        assert proof.evidence[0].cross_check == "failed"


def test_scenario_registered() -> None:
    from ophamin.measuring.scenarios.base import SCENARIOS
    assert "wilson-ci-crosscheck" in SCENARIOS
    assert SCENARIOS["wilson-ci-crosscheck"] is WilsonCICrosscheckScenario
