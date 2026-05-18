"""Tests for PearsonCrosscheckScenario (RFC 0002 Phase E1.4)."""

from __future__ import annotations

import pytest

from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
from ophamin.measuring.scenarios.pearson_crosscheck import (
    PearsonCrosscheckScenario,
)


class TestConstruction:
    def test_default(self) -> None:
        s = PearsonCrosscheckScenario()
        assert s.name == "pearson-crosscheck"
        assert s.n_pairs == 30
        assert s.sample_size == 100
        assert s.tolerance == 1e-9

    def test_invalid_n_pairs(self) -> None:
        with pytest.raises(ValueError, match="n_pairs must be"):
            PearsonCrosscheckScenario(n_pairs=0)

    def test_invalid_sample_size(self) -> None:
        with pytest.raises(ValueError, match="sample_size must be"):
            PearsonCrosscheckScenario(sample_size=2)

    def test_invalid_tolerance(self) -> None:
        with pytest.raises(ValueError, match="tolerance must be"):
            PearsonCrosscheckScenario(tolerance=0.0)

    def test_score_unreachable(self) -> None:
        s = PearsonCrosscheckScenario()
        with pytest.raises(NotImplementedError):
            s.score([], [])


class TestEndToEnd:
    def test_small_run_validates(self) -> None:
        s = PearsonCrosscheckScenario(n_pairs=10, sample_size=50)
        proof = s.run()
        assert proof.verdict.outcome == "VALIDATED"
        assert proof.evidence[0].cross_check == "passed"

    def test_three_way_agreement_at_machine_epsilon(self) -> None:
        """All three backends (scipy, numpy, pingouin) must agree at
        machine epsilon — Pearson r is computed from the same data via
        different numerical paths but reaches the same answer to
        IEEE-754 double precision.

        If this test ever fails, one of the libraries has silently
        regressed its numerical stability or default behaviour.
        """
        s = PearsonCrosscheckScenario(n_pairs=10, sample_size=50)
        proof = s.run()
        # Empirically the worst pair is scipy↔numpy (different
        # numerical paths). Even so, agreement is ≤ a few × 1e-16.
        assert proof.evidence[0].statistic_value < 1e-12, (
            f"Pearson three-way agreement drifted to "
            f"{proof.evidence[0].statistic_value:.3e} — was at "
            f"machine epsilon ~2e-16 in 0.14.0; investigate which "
            f"library changed."
        )

    def test_worst_pair_identified(self) -> None:
        """The detail dict must name which backend pair has the
        widest disagreement, so a future regression has a starting
        point.
        """
        s = PearsonCrosscheckScenario(n_pairs=5, sample_size=30)
        proof = s.run()
        worst = proof.evidence[0].detail["worst_pair"]
        assert worst in (
            "scipy_vs_numpy",
            "scipy_vs_pingouin",
            "numpy_vs_pingouin",
        )

    def test_signed_proof(self) -> None:
        s = PearsonCrosscheckScenario(n_pairs=10, sample_size=50)
        proof = s.run()
        assert proof.signature
        assert proof.verify_signature(DEFAULT_SIGN_KEY)
        assert proof.validate() == []

    def test_threshold_comparator_is_le(self) -> None:
        """Sanity: the threshold is '<=' — observed ≤ tolerance is
        the VALIDATED side.
        """
        s = PearsonCrosscheckScenario(n_pairs=5, sample_size=30)
        proof = s.run()
        assert proof.verdict.threshold.comparator == "<="
        assert proof.verdict.observed_value <= proof.verdict.threshold.value

    def test_per_pair_detail_includes_three_distances(self) -> None:
        """Each per-pair detail entry must carry all three pairwise
        distances so a reader can diagnose which axis drifted.
        """
        s = PearsonCrosscheckScenario(n_pairs=3, sample_size=30)
        proof = s.run()
        sample = proof.evidence[0].detail["sample_pairs"]
        assert len(sample) >= 3
        for entry in sample[:3]:
            assert "d_scipy_numpy" in entry
            assert "d_scipy_pingouin" in entry
            assert "d_numpy_pingouin" in entry

    def test_evidence_carries_library_versions(self) -> None:
        s = PearsonCrosscheckScenario(n_pairs=3, sample_size=30)
        proof = s.run()
        detail = proof.evidence[0].detail
        assert "scipy_version" in detail
        assert "numpy_version" in detail
        assert "pingouin_version" in detail

    def test_full_30_pair_run(self) -> None:
        """The default 30-pair run is the publishable proof shape;
        it MUST validate at the documented machine-epsilon tolerance.
        """
        s = PearsonCrosscheckScenario()  # all defaults
        proof = s.run()
        assert proof.verdict.outcome == "VALIDATED"
        assert proof.evidence[0].statistic_value <= s.tolerance


def test_scenario_registered() -> None:
    from ophamin.measuring.scenarios.base import SCENARIOS
    assert "pearson-crosscheck" in SCENARIOS
    assert SCENARIOS["pearson-crosscheck"] is PearsonCrosscheckScenario
