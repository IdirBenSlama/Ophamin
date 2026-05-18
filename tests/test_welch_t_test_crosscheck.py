"""Tests for WelchTTestCrosscheckScenario (RFC 0002 Phase E1.5)."""

from __future__ import annotations

import pytest

from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
from ophamin.measuring.scenarios.welch_t_test_crosscheck import (
    WelchTTestCrosscheckScenario,
)


class TestConstruction:
    def test_default(self) -> None:
        s = WelchTTestCrosscheckScenario()
        assert s.name == "welch-t-crosscheck"
        assert s.n_pairs == 30
        assert s.sample_size == 50
        assert s.tolerance == 1e-9

    def test_invalid_n_pairs(self) -> None:
        with pytest.raises(ValueError, match="n_pairs must be"):
            WelchTTestCrosscheckScenario(n_pairs=0)

    def test_invalid_sample_size(self) -> None:
        with pytest.raises(ValueError, match="sample_size must be"):
            WelchTTestCrosscheckScenario(sample_size=2)

    def test_invalid_tolerance(self) -> None:
        with pytest.raises(ValueError, match="tolerance must be"):
            WelchTTestCrosscheckScenario(tolerance=0.0)

    def test_score_unreachable(self) -> None:
        s = WelchTTestCrosscheckScenario()
        with pytest.raises(NotImplementedError):
            s.score([], [])


class TestEndToEnd:
    def test_small_run_validates(self) -> None:
        s = WelchTTestCrosscheckScenario(n_pairs=8, sample_size=40)
        proof = s.run()
        assert proof.verdict.outcome == "VALIDATED"
        assert proof.evidence[0].cross_check == "passed"

    def test_three_way_agreement_at_machine_epsilon(self) -> None:
        """All three Welch t-test backends must agree on BOTH the
        t-statistic and the p-value at machine epsilon. statsmodels
        is a genuinely independent implementation (it does not
        delegate to scipy), which makes this a tighter cross-check
        than the two-way Spearman case.
        """
        s = WelchTTestCrosscheckScenario(n_pairs=10, sample_size=50)
        proof = s.run()
        # Empirical baseline at 0.14.0 was ~9e-16 (a few × machine
        # epsilon). 1e-12 is a wide safety margin that still surfaces
        # any real defect loud.
        assert proof.evidence[0].statistic_value < 1e-12, (
            f"Welch t-test three-way agreement drifted to "
            f"{proof.evidence[0].statistic_value:.3e} — was at ~9e-16 "
            f"in 0.14.0; investigate which library changed "
            f"(scipy / statsmodels / pingouin)."
        )

    def test_worst_pair_and_statistic_identified(self) -> None:
        """The detail dict must name (statistic, pair) — t or p, and
        which two backends — that has the widest disagreement.
        """
        s = WelchTTestCrosscheckScenario(n_pairs=5, sample_size=30)
        proof = s.run()
        detail = proof.evidence[0].detail
        assert detail["worst_statistic"] in ("t", "p")
        assert detail["worst_pair"] in (
            "scipy_vs_statsmodels",
            "scipy_vs_pingouin",
            "statsmodels_vs_pingouin",
        )

    def test_signed_proof(self) -> None:
        s = WelchTTestCrosscheckScenario(n_pairs=8, sample_size=40)
        proof = s.run()
        assert proof.signature
        assert proof.verify_signature(DEFAULT_SIGN_KEY)
        assert proof.validate() == []

    def test_threshold_comparator_is_le(self) -> None:
        s = WelchTTestCrosscheckScenario(n_pairs=5, sample_size=30)
        proof = s.run()
        assert proof.verdict.threshold.comparator == "<="
        assert proof.verdict.observed_value <= proof.verdict.threshold.value

    def test_per_pair_detail_includes_all_three_backends(self) -> None:
        s = WelchTTestCrosscheckScenario(n_pairs=3, sample_size=30)
        proof = s.run()
        sample = proof.evidence[0].detail["sample_pairs"]
        assert len(sample) >= 3
        for entry in sample[:3]:
            for key in (
                "t_scipy", "t_statsmodels", "t_pingouin",
                "p_scipy", "p_statsmodels", "p_pingouin",
                "delta", "sigma_ratio",
            ):
                assert key in entry, f"missing {key} in per-pair detail"

    def test_evidence_carries_library_versions(self) -> None:
        s = WelchTTestCrosscheckScenario(n_pairs=3, sample_size=30)
        proof = s.run()
        detail = proof.evidence[0].detail
        assert "scipy_version" in detail
        assert "statsmodels_version" in detail
        assert "pingouin_version" in detail

    def test_full_30_pair_run(self) -> None:
        """The default 30-pair run is the publishable proof shape;
        it MUST validate at the documented machine-epsilon tolerance.
        """
        s = WelchTTestCrosscheckScenario()
        proof = s.run()
        assert proof.verdict.outcome == "VALIDATED"
        assert proof.evidence[0].statistic_value <= s.tolerance

    def test_variance_ratio_sweep_covers_both_directions(self) -> None:
        """The synthetic corpus must include both σ_y < σ_x and
        σ_y > σ_x to exercise the unequal-variance path properly.
        """
        s = WelchTTestCrosscheckScenario(n_pairs=30, sample_size=30)
        proof = s.run()
        sample = proof.evidence[0].detail["sample_pairs"]
        ratios = [entry["sigma_ratio"] for entry in sample]
        assert any(r < 1.0 for r in ratios), "no σ_y < σ_x pairs"
        assert any(r > 1.0 for r in ratios), "no σ_y > σ_x pairs"


def test_scenario_registered() -> None:
    from ophamin.measuring.scenarios.base import SCENARIOS
    assert "welch-t-crosscheck" in SCENARIOS
    assert SCENARIOS["welch-t-crosscheck"] is WelchTTestCrosscheckScenario
