"""Tests for graded_fidelity + the path-magnitude-fidelity scenario object.

graded_fidelity is the fix for the binary-separation flaw the review found: it
scores a representation by whether its distances SCALE with a graded quantity,
and returns 0 for a saturated (binary-detector) distance — so a system that only
says "different/same" cannot pass a test that demands "how different".
"""

from __future__ import annotations

import pytest

from ophamin.comparing.retrieval_baseline import graded_fidelity
from ophamin.measuring.scenarios.finance_path_magnitude_fidelity import (
    FinancePathMagnitudeFidelityScenario,
)


class TestGradedFidelity:
    def test_perfectly_monotonic_is_one(self):
        assert graded_fidelity([1, 2, 3, 4, 5], [10, 20, 30, 40, 50]) == pytest.approx(1.0)

    def test_anti_monotonic_is_minus_one(self):
        assert graded_fidelity([5, 4, 3, 2, 1], [10, 20, 30, 40, 50]) == pytest.approx(-1.0)

    def test_saturated_distance_scores_zero(self):
        # the binary-detector failure mode: every distance ~1.0 -> no graded signal
        assert graded_fidelity([1.0, 1.0, 1.0, 1.0], [1, 2, 3, 4]) == 0.0

    def test_constant_target_scores_zero(self):
        assert graded_fidelity([1, 2, 3, 4], [7, 7, 7, 7]) == 0.0

    def test_too_few_points_zero(self):
        assert graded_fidelity([1, 2], [1, 2]) == 0.0

    def test_mismatched_lengths_zero(self):
        assert graded_fidelity([1, 2, 3], [1, 2]) == 0.0

    def test_partial_correlation_in_range(self):
        rho = graded_fidelity([1, 2, 3, 4, 5], [1, 3, 2, 5, 4])
        assert 0.0 < rho < 1.0


class TestScenarioObject:
    _MS = (0.01, -0.02, 0.03, -0.04, 0.02)

    def _scn(self, **kw):
        base = dict(return_windows=(self._MS,), n_orderings=8)
        base.update(kw)
        return FinancePathMagnitudeFidelityScenario(**base)

    def test_claim_threshold_is_graded_advantage(self):
        claim = self._scn(advantage_margin=0.2).build_claim()
        assert claim.threshold.metric == "graded_fidelity_advantage"
        assert claim.threshold.comparator == ">="
        assert claim.threshold.value == 0.2

    def test_orderings_are_permutations_of_the_multiset(self):
        variants = self._scn()._orderings(self._MS)
        assert len(variants) >= 3
        for v in variants:
            assert sorted(v) == sorted(self._MS)  # same multiset, different order

    def test_run_without_substrate_raises(self):
        with pytest.raises(ValueError):
            self._scn().run(substrate=None)

    def test_score_is_unreachable(self):
        with pytest.raises(NotImplementedError):
            self._scn().score([], [])

    def test_rejects_short_window(self):
        with pytest.raises(ValueError):
            FinancePathMagnitudeFidelityScenario(return_windows=((0.1, -0.1, 0.2),))
