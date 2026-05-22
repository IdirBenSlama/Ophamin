"""Tests for the finance-history-discrimination proof — Kimera separating
real-risk-different same-set histories vs an order-invariant baseline.

Fake adapter, two modes (prime_chain parsed-from-return-events):
  * ``mode="discriminating"`` — prime_chain depends on the ORDER → the min-DD and
    max-DD orderings get different addresses → Kimera separates → VALIDATED.
  * ``mode="conflating"``     — prime_chain depends only on the MULTISET → both
    orderings get the same address → Kimera conflates (like RAG) → not VALIDATED.
"""

from __future__ import annotations

import hashlib
import re

import pytest

from ophamin.measuring.scenarios import SCENARIOS
from ophamin.measuring.scenarios.finance_history_discrimination import (
    FinanceHistoryDiscriminationScenario,
)
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest

_RET = re.compile(r"return ([+-]?\d+\.\d+)")


class _DiscAdapter(SubstrateUnderTest):
    def __init__(self, *, mode: str = "discriminating") -> None:
        self.name = "disc-fake"
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
        returns = [float(_RET.search(t).group(1)) if _RET.search(t) else 0.0 for t in texts]
        if self._mode == "discriminating":
            key = "|".join(f"{r:+.4f}" for r in returns)             # order-sensitive
        elif self._mode == "conflating":
            key = "|".join(f"{r:+.4f}" for r in sorted(returns))     # multiset only
        else:  # pragma: no cover
            raise ValueError(self._mode)
        h = hashlib.sha256(key.encode()).hexdigest()
        chain = [int(h[j:j + 4], 16) for j in range(0, 32, 4)]
        out = []
        for i, t in enumerate(texts):
            out.append(CycleResult(cycle_index=i, success=True, halt_mode="exhausted",
                                   raw={"prime_chain": chain}))
        return out


# mixed-sign windows so min-DD and max-DD orderings differ a lot
_WINDOWS = (
    (0.02, -0.05, 0.03, -0.04, 0.01, -0.06),
    (-0.03, 0.04, -0.05, 0.02, 0.06, -0.02),
    (0.01, 0.02, -0.07, 0.03, -0.01, 0.05),
    (-0.04, -0.02, 0.05, 0.01, -0.03, 0.04),
    (0.03, -0.06, 0.02, -0.05, 0.04, -0.01),
)


def _scenario(**kw):
    kw.setdefault("return_windows", _WINDOWS)
    kw.setdefault("search_shuffles", 80)
    kw.setdefault("min_windows", 4)
    return FinanceHistoryDiscriminationScenario(**kw)


class TestMinMaxSearch:
    def test_finds_distinct_drawdown_orderings(self):
        s = _scenario()
        lo, lo_dd, hi, hi_dd = s._min_max_dd_orderings(_WINDOWS[0])
        assert hi_dd > lo_dd               # max-DD ordering has bigger drawdown
        assert sorted(lo) == sorted(hi)    # same multiset


class TestVerdict:
    def test_discriminating_validated(self):
        rec = _scenario().run(_DiscAdapter(mode="discriminating"))
        assert rec.verdict.outcome == "VALIDATED"
        ev = rec.evidence[0]
        assert ev.statistic_name == "history_separation_advantage"
        assert ev.statistic_value > 0.0
        d = ev.detail
        assert d["separation_rate"] == pytest.approx(1.0)
        assert d["rag_representation_distance_mean"] == pytest.approx(0.0, abs=1e-6)
        assert d["delta_drawdown_mean"] > 0.0   # the histories really differ in risk

    def test_conflating_not_validated(self):
        rec = _scenario().run(_DiscAdapter(mode="conflating"))
        assert rec.verdict.outcome != "VALIDATED"
        d = rec.evidence[0].detail
        assert d["kimera_prime_distance_mean"] == pytest.approx(0.0)

    def test_claim_scope_is_discrimination_not_magnitude(self):
        rec = _scenario().run(_DiscAdapter(mode="discriminating"))
        d = rec.evidence[0].detail
        assert d["claim_scope"] == "discrimination_not_magnitude"
        assert "does NOT grade" in d["gradedness_limit"]


class TestContract:
    def test_registered_and_comparison_scoped(self):
        assert "finance-history-discrimination" in SCENARIOS
        s = _scenario()
        assert s.scope == "comparison"
        assert s.family == "memory"

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            FinanceHistoryDiscriminationScenario(return_windows=())

    def test_missing_substrate_raises(self):
        with pytest.raises(ValueError, match="live substrate"):
            _scenario().run(None)

    def test_signed_proof_verifies(self):
        from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
        rec = _scenario().run(_DiscAdapter(mode="discriminating"))
        assert rec.signature
        assert rec.verify_signature(DEFAULT_SIGN_KEY) is True
