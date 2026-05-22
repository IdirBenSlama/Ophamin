"""Tests for the finance-path-dependence proof — Kimera tracking order-dependent
drawdown vs an order-invariant baseline.

A fake adapter parses the return from each event text and sets its manifold
state by a chosen rule:

  * ``mode="tracking"``    — coupling encodes the max drawdown of the sequence it
    saw (path-dependent) → state-divergence tracks ΔMDD → rho > 0 → VALIDATED.
  * ``mode="blind"``       — coupling encodes the SUM of returns (order-invariant)
    → identical for true and shuffle → no state variance → not VALIDATED.
"""

from __future__ import annotations

import re

import pytest

from ophamin.measuring.scenarios import SCENARIOS
from ophamin.measuring.scenarios.finance_path_dependence import (
    FinancePathDependenceScenario,
)
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest

_RET = re.compile(r"return ([+-]?\d+\.\d+)")


def _max_dd(returns):
    import numpy as np
    r = np.asarray(returns, float)
    prices = np.cumprod(1.0 + r)
    peak = np.maximum.accumulate(prices)
    return float(abs((prices / peak - 1.0).min())) if r.size else 0.0


class _FinanceAdapter(SubstrateUnderTest):
    def __init__(self, *, mode: str = "tracking") -> None:
        self.name = "fin-fake"
        self._mode = mode

    def git_commit(self) -> str:
        return "fakecommit01"

    def reset(self) -> None:
        pass

    def metadata(self) -> dict:
        return {"name": self.name, "git_commit": self.git_commit()}

    def run_cycle(self, stimulus, params=None) -> CycleResult:  # pragma: no cover
        return self.run_batch([stimulus])[0]

    def run_batch(self, texts, params=None) -> list[CycleResult]:
        returns: list[float] = []
        out: list[CycleResult] = []
        for i, t in enumerate(texts):
            m = _RET.search(t)
            returns.append(float(m.group(1)) if m else 0.0)
            if self._mode == "tracking":
                coupling = 100.0 + 50.0 * _max_dd(returns)        # path-dependent
            elif self._mode == "blind":
                coupling = 100.0 + sum(returns)                   # order-invariant
            else:  # pragma: no cover
                raise ValueError(self._mode)
            out.append(CycleResult(
                cycle_index=i, success=True, halt_mode="exhausted",
                raw={
                    "arachne_web_coupling_frobenius": coupling,
                    "arachne_web_order_parameter": 0.5,
                    "knowledge_mass": 10.0,
                    "prime_chain": [int(abs(r) * 1e6) % 9973 for r in returns],
                },
            ))
        return out


# real-ish return windows with mixed signs so order changes drawdown
_WINDOWS = (
    (0.02, -0.05, 0.03, -0.04, 0.01, -0.06),
    (-0.03, 0.04, -0.05, 0.02, 0.06, -0.02),
    (0.01, 0.02, -0.07, 0.03, -0.01, 0.05),
    (-0.04, -0.02, 0.05, 0.01, -0.03, 0.04),
    (0.03, -0.06, 0.02, -0.05, 0.04, -0.01),
)


def _scenario(**kw):
    kw.setdefault("return_windows", _WINDOWS)
    kw.setdefault("n_shuffles", 3)
    kw.setdefault("min_points", 8)
    return FinancePathDependenceScenario(**kw)


class TestGroundTruth:
    def test_max_drawdown_is_order_dependent(self):
        a = FinancePathDependenceScenario._max_drawdown((0.1, -0.2, 0.15, -0.1))
        b = FinancePathDependenceScenario._max_drawdown((-0.2, -0.1, 0.1, 0.15))
        assert a != pytest.approx(b)  # same multiset, different order, different MDD

    def test_render_event_is_numeric_forward(self):
        ev = FinancePathDependenceScenario._render_event(0, -0.0423)
        assert "-0.0423" in ev


class TestVerdict:
    def test_tracking_validated(self):
        rec = _scenario().run(_FinanceAdapter(mode="tracking"))
        assert rec.verdict.outcome == "VALIDATED"
        ev = rec.evidence[0]
        assert ev.statistic_name == "drawdown_tracking_rho"
        assert ev.statistic_value > 0.0
        assert ev.p_value is not None and ev.p_value < 0.05
        assert ev.cross_check == "passed"
        # the structural contrast: RAG representation is order-invariant
        assert ev.detail["rag_representation_divergence_mean"] == pytest.approx(0.0, abs=1e-6)

    def test_blind_not_validated(self):
        rec = _scenario().run(_FinanceAdapter(mode="blind"))
        assert rec.verdict.outcome != "VALIDATED"
        # order-invariant state → no divergence to track drawdown with
        assert rec.evidence[0].detail["kimera_state_divergence_mean"] == pytest.approx(0.0)

    def test_rag_contrast_is_zero(self):
        rec = _scenario().run(_FinanceAdapter(mode="tracking"))
        d = rec.evidence[0].detail
        assert d["rag_representation_divergence_mean"] == pytest.approx(0.0, abs=1e-6)
        assert all(p["rag_representation_divergence"] == pytest.approx(0.0, abs=1e-6)
                   for p in d["per_pair"])


class TestContract:
    def test_registered_and_comparison_scoped(self):
        assert "finance-path-dependence" in SCENARIOS
        s = _scenario()
        assert s.scope == "comparison"
        assert s.family == "memory"
        assert s.tier.value == "scientific"

    def test_rejects_empty_windows(self):
        with pytest.raises(ValueError):
            FinancePathDependenceScenario(return_windows=())

    def test_rejects_short_window(self):
        with pytest.raises(ValueError, match=">= 3"):
            FinancePathDependenceScenario(return_windows=((0.1, 0.2),))

    def test_missing_substrate_raises(self):
        with pytest.raises(ValueError, match="live substrate"):
            _scenario().run(None)

    def test_signed_proof_verifies(self):
        from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
        rec = _scenario().run(_FinanceAdapter(mode="tracking"))
        assert rec.signature
        assert rec.verify_signature(DEFAULT_SIGN_KEY) is True
