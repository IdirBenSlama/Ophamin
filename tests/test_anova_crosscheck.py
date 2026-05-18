"""Tests for OneWayAnovaCrosscheckScenario (RFC 0002 Phase E1.6)."""

from __future__ import annotations

import pytest

from ophamin.measuring.scenarios.anova_crosscheck import (
    OneWayAnovaCrosscheckScenario,
)
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY


class TestConstruction:
    def test_default(self) -> None:
        s = OneWayAnovaCrosscheckScenario()
        assert s.name == "anova-crosscheck"
        assert s.n_datasets == 30
        assert s.sample_size == 30
        assert s.tolerance == 1e-9

    def test_invalid_n_datasets(self) -> None:
        with pytest.raises(ValueError, match="n_datasets must be"):
            OneWayAnovaCrosscheckScenario(n_datasets=0)

    def test_invalid_sample_size(self) -> None:
        with pytest.raises(ValueError, match="sample_size must be"):
            OneWayAnovaCrosscheckScenario(sample_size=2)

    def test_invalid_tolerance(self) -> None:
        with pytest.raises(ValueError, match="tolerance must be"):
            OneWayAnovaCrosscheckScenario(tolerance=0.0)

    def test_score_unreachable(self) -> None:
        s = OneWayAnovaCrosscheckScenario()
        with pytest.raises(NotImplementedError):
            s.score([], [])


class TestEndToEnd:
    def test_small_run_validates(self) -> None:
        s = OneWayAnovaCrosscheckScenario(n_datasets=8, sample_size=20)
        proof = s.run()
        assert proof.verdict.outcome == "VALIDATED"
        assert proof.evidence[0].cross_check == "passed"

    def test_three_way_agreement_at_machine_epsilon(self) -> None:
        """All three ANOVA backends must agree on BOTH F and p at
        machine epsilon. statsmodels (via OLS+anova_lm) is a
        genuinely independent path, so this is a tighter cross-
        check than Spearman's two-way.
        """
        s = OneWayAnovaCrosscheckScenario(n_datasets=10, sample_size=25)
        proof = s.run()
        # Empirical baseline at 0.15.0 was ~3e-14. 1e-9 is the loud-
        # failure threshold for a real upstream defect.
        assert proof.evidence[0].statistic_value < 1e-9, (
            f"One-way ANOVA three-way agreement drifted to "
            f"{proof.evidence[0].statistic_value:.3e} — was at ~3e-14 "
            f"in 0.15.0; investigate which library changed."
        )

    def test_worst_pair_and_statistic_identified(self) -> None:
        s = OneWayAnovaCrosscheckScenario(n_datasets=5, sample_size=15)
        proof = s.run()
        detail = proof.evidence[0].detail
        assert detail["worst_statistic"] in ("F", "p")
        assert detail["worst_pair"] in (
            "scipy_vs_statsmodels",
            "scipy_vs_pingouin",
            "statsmodels_vs_pingouin",
        )

    def test_signed_proof(self) -> None:
        s = OneWayAnovaCrosscheckScenario(n_datasets=8, sample_size=20)
        proof = s.run()
        assert proof.signature
        assert proof.verify_signature(DEFAULT_SIGN_KEY)
        assert proof.validate() == []

    def test_threshold_comparator_is_le(self) -> None:
        s = OneWayAnovaCrosscheckScenario(n_datasets=5, sample_size=15)
        proof = s.run()
        assert proof.verdict.threshold.comparator == "<="
        assert proof.verdict.observed_value <= proof.verdict.threshold.value

    def test_per_dataset_detail_includes_all_three_backends(self) -> None:
        s = OneWayAnovaCrosscheckScenario(n_datasets=3, sample_size=15)
        proof = s.run()
        sample = proof.evidence[0].detail["sample_datasets"]
        assert len(sample) >= 3
        for entry in sample[:3]:
            for key in (
                "F_scipy", "F_statsmodels", "F_pingouin",
                "p_scipy", "p_statsmodels", "p_pingouin",
                "effect_magnitude",
            ):
                assert key in entry, f"missing {key} in per-dataset detail"

    def test_evidence_carries_library_versions(self) -> None:
        s = OneWayAnovaCrosscheckScenario(n_datasets=3, sample_size=15)
        proof = s.run()
        detail = proof.evidence[0].detail
        assert "scipy_version" in detail
        assert "statsmodels_version" in detail
        assert "pingouin_version" in detail

    def test_full_30_dataset_run(self) -> None:
        """The default 30-dataset run is the publishable proof shape;
        it MUST validate at the documented machine-epsilon tolerance.
        """
        s = OneWayAnovaCrosscheckScenario()
        proof = s.run()
        assert proof.verdict.outcome == "VALIDATED"
        assert proof.evidence[0].statistic_value <= s.tolerance

    def test_effect_sweep_documented_in_analysis_plan(self) -> None:
        """The synthetic corpus exercises a sweep from null (small
        effect) to clearly-alternative (large effect), so the
        cross-check covers both small-F and large-F paths. The
        sweep range is part of the scenario's pre-registered plan.
        """
        s = OneWayAnovaCrosscheckScenario(n_datasets=20, sample_size=20)
        plan = s.analysis_plan()
        # The plan must explicitly call out the null-to-large sweep.
        assert "null to 1.5" in plan
        # And the verdict must validate across that whole sweep.
        proof = s.run()
        assert proof.verdict.outcome == "VALIDATED"


def test_scenario_registered() -> None:
    from ophamin.measuring.scenarios.base import SCENARIOS
    assert "anova-crosscheck" in SCENARIOS
    assert SCENARIOS["anova-crosscheck"] is OneWayAnovaCrosscheckScenario
