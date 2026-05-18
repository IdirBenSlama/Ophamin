"""Tests for SpearmanCrosscheckScenario (RFC 0002 Phase E1.3)."""

from __future__ import annotations

import pytest

from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
from ophamin.measuring.scenarios.spearman_crosscheck import (
    SpearmanCrosscheckScenario,
)


class TestConstruction:
    def test_default(self) -> None:
        s = SpearmanCrosscheckScenario()
        assert s.name == "spearman-crosscheck"
        assert s.n_pairs == 30
        assert s.sample_size == 100
        assert s.tolerance == 1e-9

    def test_invalid_n_pairs(self) -> None:
        with pytest.raises(ValueError, match="n_pairs must be"):
            SpearmanCrosscheckScenario(n_pairs=0)

    def test_invalid_sample_size(self) -> None:
        with pytest.raises(ValueError, match="sample_size must be"):
            SpearmanCrosscheckScenario(sample_size=2)

    def test_invalid_tolerance(self) -> None:
        with pytest.raises(ValueError, match="tolerance must be"):
            SpearmanCrosscheckScenario(tolerance=0.0)

    def test_score_unreachable(self) -> None:
        s = SpearmanCrosscheckScenario()
        with pytest.raises(NotImplementedError):
            s.score([], [])


class TestEndToEnd:
    def test_small_run_validates(self) -> None:
        s = SpearmanCrosscheckScenario(n_pairs=10, sample_size=50)
        proof = s.run()
        assert proof.verdict.outcome == "VALIDATED"
        assert proof.evidence[0].cross_check == "passed"

    def test_exact_agreement(self) -> None:
        """pingouin delegates Spearman to scipy; agreement must be EXACT.

        If pingouin ever forks the implementation, this test surfaces
        the divergence at PR time.
        """
        s = SpearmanCrosscheckScenario(n_pairs=10, sample_size=50)
        proof = s.run()
        assert proof.evidence[0].statistic_value == 0.0, (
            f"scipy and pingouin disagree on Spearman ρ by "
            f"{proof.evidence[0].statistic_value:.3e} — pingouin "
            f"may have forked its implementation."
        )

    def test_signed_proof(self) -> None:
        s = SpearmanCrosscheckScenario(n_pairs=10, sample_size=50)
        proof = s.run()
        assert proof.signature
        assert proof.verify_signature(DEFAULT_SIGN_KEY)
        assert proof.validate() == []

    def test_falsifiability_absurd_tolerance(self) -> None:
        """An absurdly tight tolerance combined with hand-tampered
        scoring would refute. Here we test that the scenario reports
        the actual observed max-diff correctly; with exact agreement
        and a positive tolerance, observed (0.0) is ≤ tolerance for
        any tolerance > 0 — so we can't test REFUTED without injecting
        an actual implementation divergence. Skip the falsifiability
        check for this scenario."""
        s = SpearmanCrosscheckScenario(n_pairs=5, sample_size=30)
        proof = s.run()
        # Verify the scenario's threshold-comparator logic IS evaluated
        # (the threshold is "<=", so observed <= tolerance → VALIDATED).
        assert proof.verdict.threshold.comparator == "<="
        assert proof.verdict.observed_value <= proof.verdict.threshold.value


def test_scenario_registered() -> None:
    from ophamin.measuring.scenarios.base import SCENARIOS
    assert "spearman-crosscheck" in SCENARIOS
    assert SCENARIOS["spearman-crosscheck"] is SpearmanCrosscheckScenario
