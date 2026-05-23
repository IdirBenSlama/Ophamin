"""Tests for graded_fidelity + the path-magnitude-fidelity scenario object.

graded_fidelity is the fix for the binary-separation flaw the review found: it
scores a representation by whether its distances SCALE with a graded quantity,
and returns 0 for a saturated (binary-detector) distance — so a system that only
says "different/same" cannot pass a test that demands "how different".
"""

from __future__ import annotations

import math
import re

import pytest

from ophamin.comparing.retrieval_baseline import graded_fidelity
from ophamin.measuring.scenarios.finance_path_dependence import (
    FinancePathDependenceScenario,
)
from ophamin.measuring.scenarios.finance_path_magnitude_fidelity import (
    FinancePathMagnitudeFidelityScenario,
)
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest

_mdd = FinancePathDependenceScenario._max_drawdown


class _FakeGradingSubstrate(SubstrateUnderTest):
    """A substrate whose manifold state strictly grades |Δ max-drawdown|.

    Emits ``coupling = exp(20·mdd)`` so the relative state-divergence between two
    orderings is ``tanh(10·|Δmdd|)`` — strictly increasing in ``|Δmdd|``, hence
    fidelity_state → 1.0. The ``prime_chain`` is constant, so the prime
    set-distance is identically 0 → fidelity_prime 0 (the saturated control).
    This exercises the state-primary ``run()`` path end to end without Kimera.
    """

    name = "fake-grading"

    def git_commit(self) -> str:
        return "fake0000feed"

    def reset(self) -> None:
        return None

    def run_cycle(self, stimulus, params=None):  # pragma: no cover - batch path used
        return CycleResult(cycle_index=0, success=True, raw={})

    def run_batch(self, stimuli, params=None):
        returns = []
        for s in stimuli:
            m = re.search(r"return\s+([+-]?[0-9.]+)", str(s))
            if m:
                returns.append(float(m.group(1)))
        mdd = _mdd(tuple(returns)) if returns else 0.0
        raw = {
            "arachne_web_coupling_frobenius": math.exp(20.0 * mdd),
            "prime_chain": ["2", "3", "5"],  # constant → saturated control
        }
        return [
            CycleResult(cycle_index=i, success=True, raw=dict(raw))
            for i in range(max(1, len(stimuli)))
        ]


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

    def test_field_contract_requires_manifold_state_not_prime(self):
        fc = self._scn().field_contract()
        required = {c.field_name for c in fc.contracts if c.required}
        assert "arachne_web_coupling_frobenius" in required
        # the prime readout is now only a saturation control — not required
        prime = next(c for c in fc.contracts if c.field_name == "prime_chain")
        assert prime.required is False

    def test_state_is_primary_readout_and_prime_is_saturated_control(self):
        windows = (
            (0.02, -0.03, 0.05, -0.01, 0.04),
            (0.01, -0.05, 0.02, 0.03, -0.02),
            (-0.04, 0.06, -0.02, 0.01, 0.03),
            (0.03, 0.02, -0.06, 0.04, -0.01),
            (-0.01, 0.05, -0.03, 0.02, -0.04),
        )
        scn = FinancePathMagnitudeFidelityScenario(
            return_windows=windows, n_orderings=12, advantage_margin=0.2,
        )
        rec = scn.run(_FakeGradingSubstrate())
        ev = rec.evidence[0]
        assert ev.statistic_name == "graded_fidelity_advantage"
        assert ev.detail["primary_readout"] == "manifold_state_divergence"
        wins = [w for w in ev.detail["per_window"] if not w.get("gap")]
        assert len(wins) >= scn.min_windows
        for w in wins:
            # state grades strictly → high fidelity; constant primes → 0 control
            assert w["fidelity_state"] >= 0.9
            assert w["fidelity_prime"] == 0.0
        # headline is the state advantage over the order-aware bar → VALIDATED
        assert ev.statistic_value >= 0.2
        assert rec.verdict.outcome == "VALIDATED"

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
