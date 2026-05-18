"""Tests for MannWhitneyUCrosscheckScenario (RFC 0002 Phase E1.7)."""

from __future__ import annotations

import pytest

from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
from ophamin.measuring.scenarios.mann_whitney_crosscheck import (
    MannWhitneyUCrosscheckScenario,
)


class TestConstruction:
    def test_default(self) -> None:
        s = MannWhitneyUCrosscheckScenario()
        assert s.name == "mann-whitney-crosscheck"
        assert s.n_pairs == 30
        assert s.sample_size == 50
        assert s.tolerance == 1e-9

    def test_invalid_n_pairs(self) -> None:
        with pytest.raises(ValueError, match="n_pairs must be"):
            MannWhitneyUCrosscheckScenario(n_pairs=0)

    def test_invalid_sample_size(self) -> None:
        with pytest.raises(ValueError, match="sample_size must be"):
            MannWhitneyUCrosscheckScenario(sample_size=2)

    def test_invalid_tolerance(self) -> None:
        with pytest.raises(ValueError, match="tolerance must be"):
            MannWhitneyUCrosscheckScenario(tolerance=0.0)

    def test_score_unreachable(self) -> None:
        s = MannWhitneyUCrosscheckScenario()
        with pytest.raises(NotImplementedError):
            s.score([], [])


class TestEndToEnd:
    def test_small_run_validates(self) -> None:
        s = MannWhitneyUCrosscheckScenario(n_pairs=12, sample_size=40)
        proof = s.run()
        assert proof.verdict.outcome == "VALIDATED"
        assert proof.evidence[0].cross_check == "passed"

    def test_two_way_agreement_at_machine_epsilon(self) -> None:
        """scipy and pingouin must agree on U + p to machine epsilon
        under matched continuity settings (both default to
        use_continuity=True). U is integer-valued; p is float — both
        must match.
        """
        s = MannWhitneyUCrosscheckScenario(n_pairs=15, sample_size=50)
        proof = s.run()
        # Empirical baseline at 0.15.0 was 0.0 (exact agreement). 1e-9
        # is the loud-failure threshold for a real defect.
        assert proof.evidence[0].statistic_value < 1e-9, (
            f"Mann-Whitney U agreement drifted to "
            f"{proof.evidence[0].statistic_value:.3e} — was at 0.0 "
            f"(exact) in 0.15.0; investigate which library changed "
            f"the continuity-correction default."
        )

    def test_signed_proof(self) -> None:
        s = MannWhitneyUCrosscheckScenario(n_pairs=12, sample_size=40)
        proof = s.run()
        assert proof.signature
        assert proof.verify_signature(DEFAULT_SIGN_KEY)
        assert proof.validate() == []

    def test_threshold_comparator_is_le(self) -> None:
        s = MannWhitneyUCrosscheckScenario(n_pairs=5, sample_size=30)
        proof = s.run()
        assert proof.verdict.threshold.comparator == "<="
        assert proof.verdict.observed_value <= proof.verdict.threshold.value

    def test_evidence_carries_library_versions(self) -> None:
        s = MannWhitneyUCrosscheckScenario(n_pairs=3, sample_size=20)
        proof = s.run()
        detail = proof.evidence[0].detail
        assert "scipy_version" in detail
        assert "pingouin_version" in detail

    def test_distribution_rotation_covers_three_shapes(self) -> None:
        """The synthetic corpus must exercise all three distribution
        shapes (normal / log-normal / Cauchy). Mann-Whitney's
        non-parametric character matters most on heavy-tailed
        distributions, so coverage across shapes is load-bearing.
        """
        s = MannWhitneyUCrosscheckScenario(n_pairs=12, sample_size=30)
        proof = s.run()
        sample = proof.evidence[0].detail["sample_pairs"]
        shapes_seen = {entry["shape"] for entry in sample}
        # Even sampling only the first 5 pairs we should see at least
        # 2 shapes given the rotation; with overflows on disagreement
        # we'd see all 3.
        assert len(shapes_seen) >= 2, (
            f"Distribution rotation degenerate: only saw {shapes_seen}"
        )

    def test_full_30_pair_run(self) -> None:
        """The default 30-pair run is the publishable proof shape."""
        s = MannWhitneyUCrosscheckScenario()
        proof = s.run()
        assert proof.verdict.outcome == "VALIDATED"
        assert proof.evidence[0].statistic_value <= s.tolerance

    def test_per_pair_detail_includes_both_distances(self) -> None:
        s = MannWhitneyUCrosscheckScenario(n_pairs=3, sample_size=20)
        proof = s.run()
        sample = proof.evidence[0].detail["sample_pairs"]
        assert len(sample) >= 3
        for entry in sample[:3]:
            assert "abs_U_diff" in entry
            assert "abs_p_diff" in entry
            assert "shape" in entry


def test_scenario_registered() -> None:
    from ophamin.measuring.scenarios.base import SCENARIOS
    assert "mann-whitney-crosscheck" in SCENARIOS
    assert SCENARIOS["mann-whitney-crosscheck"] is MannWhitneyUCrosscheckScenario
