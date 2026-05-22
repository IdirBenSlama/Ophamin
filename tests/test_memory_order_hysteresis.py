"""Tests for the memory-order-hysteresis proof — Kimera vs order-invariant RAG.

A programmable fake adapter models the three worlds the proof must distinguish,
emitting a real ``prime_chain`` per cycle (the probe's prime-address):

  * ``mode="hysteresis"``      — the prime-address depends on the ORDER of
    preceding documents (deterministic for identical order). Same docs in a
    different order → different address; identical order twice → identical
    address. order_hysteresis > 0, noise ≈ 0 → VALIDATED.
  * ``mode="commutative"``     — the address depends only on the SET of
    preceding documents (order-blind, like RAG). order_divergence = noise = 0 →
    order_hysteresis = 0 → REFUTED (the honest "accumulation is commutative").
  * ``mode="nondeterministic"``— the address is random each run; noise swamps
    any order effect → not VALIDATED (the determinism control does its job).
"""

from __future__ import annotations

import hashlib
import random

import pytest

from ophamin.measuring.scenarios import SCENARIOS
from ophamin.measuring.scenarios.memory_order_hysteresis import (
    MemoryOrderHysteresisScenario,
)
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest


class _HysteresisAdapter(SubstrateUnderTest):
    """Emits a prime_chain whose order-sensitivity is set by ``mode``."""

    def __init__(self, *, mode: str = "hysteresis") -> None:
        self.name = "hyst-fake"
        self._mode = mode
        self._rng = random.Random(42)

    def git_commit(self) -> str:
        return "fakecommit01"

    def reset(self) -> None:
        self._rng = random.Random(42)

    def metadata(self) -> dict:
        return {"name": self.name, "git_commit": self.git_commit()}

    def run_cycle(self, stimulus, params=None) -> CycleResult:  # pragma: no cover
        return self.run_batch([stimulus])[0]

    def run_batch(self, texts, params=None) -> list[CycleResult]:
        out: list[CycleResult] = []
        for i, t in enumerate(texts):
            preceding = list(texts[:i])
            if self._mode == "hysteresis":
                key = t + "||" + "|".join(preceding)            # order-sensitive
            elif self._mode == "commutative":
                key = t + "||" + "|".join(sorted(preceding))    # order-blind (set)
            elif self._mode == "nondeterministic":
                key = t + "||" + str(self._rng.random())        # run-noise
            else:  # pragma: no cover
                raise ValueError(f"unknown mode {self._mode!r}")
            h = hashlib.sha256(key.encode()).hexdigest()
            chain = [int(h[j:j + 4], 16) for j in range(0, 32, 4)]  # 8 pseudo-primes
            concepts = [w.lower() for w in t.split()[:5]]  # recognition stable
            out.append(CycleResult(
                cycle_index=i, success=True, halt_mode="exhausted",
                raw={
                    "prime_chain": chain,
                    "concepts": concepts,
                    "arachne_web_coupling_frobenius": float(len(preceding)),
                    "knowledge_mass": float(len(preceding)),
                    "arachne_web_order_parameter": 0.5,
                },
            ))
        return out


def _docs(n=6):
    return tuple(f"document {i} about topic {i} with detail {i}" for i in range(n))


def _probes(n=6):
    return tuple(f"query {i} asking about matter {i} and aspect {i}" for i in range(n))


def _scenario(**kw):
    kw.setdefault("documents", _docs(6))
    kw.setdefault("probes", _probes(6))
    kw.setdefault("min_probes", 4)
    return MemoryOrderHysteresisScenario(**kw)


class TestVerdict:
    def test_hysteresis_world_validated(self):
        rec = _scenario().run(_HysteresisAdapter(mode="hysteresis"))
        assert rec.verdict.outcome == "VALIDATED"
        ev = rec.evidence[0]
        assert ev.statistic_name == "order_hysteresis"
        assert ev.statistic_value > 0.0
        d = ev.detail
        assert d["kimera_order_divergence_mean"] > d["kimera_noise_floor_mean"]
        assert d["kimera_noise_floor_mean"] == pytest.approx(0.0)  # determinism
        assert d["rag_baseline_order_divergence_mean"] == pytest.approx(0.0)
        assert ev.cross_check == "passed"
        assert ev.p_value is not None and ev.p_value < 0.05

    def test_commutative_world_refuted(self):
        # recognises + accumulates, but order does NOT matter → not hysteresis
        rec = _scenario().run(_HysteresisAdapter(mode="commutative"))
        assert rec.verdict.outcome == "REFUTED"
        d = rec.evidence[0].detail
        assert d["order_hysteresis"] == pytest.approx(0.0)
        assert d["kimera_order_divergence_mean"] == pytest.approx(0.0)

    def test_nondeterministic_not_validated(self):
        # run-noise swamps the order effect → the determinism control prevents
        # a false VALIDATED
        rec = _scenario().run(_HysteresisAdapter(mode="nondeterministic"))
        assert rec.verdict.outcome != "VALIDATED"
        d = rec.evidence[0].detail
        assert d["kimera_noise_floor_mean"] > 0.0  # noise is high here

    def test_baseline_is_order_invariant(self):
        rec = _scenario().run(_HysteresisAdapter(mode="hysteresis"))
        d = rec.evidence[0].detail
        assert d["rag_baseline_order_divergence_mean"] == pytest.approx(0.0)
        assert all(b["identical_ranking"] for b in d["rag_baseline"])

    def test_manifold_state_order_effect_recorded(self):
        rec = _scenario().run(_HysteresisAdapter(mode="hysteresis"))
        d = rec.evidence[0].detail
        assert "manifold_state_order_effect" in d
        assert "manifold_state_noise_floor" in d


class TestContract:
    def test_registered_and_comparison_scoped(self):
        assert "memory-order-hysteresis" in SCENARIOS
        s = _scenario()
        assert s.scope == "comparison"
        assert s.family == "memory"
        assert s.tier.value == "scientific"

    def test_documents_probes_disjoint_enforced(self):
        shared = _docs(4)
        with pytest.raises(ValueError, match="disjoint"):
            MemoryOrderHysteresisScenario(documents=shared, probes=shared[:2])

    def test_needs_two_documents(self):
        with pytest.raises(ValueError, match="2 documents"):
            MemoryOrderHysteresisScenario(documents=("only one",), probes=_probes(4))

    def test_missing_substrate_raises(self):
        with pytest.raises(ValueError, match="live substrate"):
            _scenario().run(None)

    def test_order_b_is_different(self):
        s = _scenario()
        assert s._order_b() != list(s.documents)
        assert set(s._order_b()) == set(s.documents)  # same set, different order

    def test_signed_proof_verifies(self):
        from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
        rec = _scenario().run(_HysteresisAdapter(mode="hysteresis"))
        assert rec.signature
        assert rec.verify_signature(DEFAULT_SIGN_KEY) is True


class TestExtraction:
    def test_prime_set_from_chain(self):
        r = CycleResult(cycle_index=0, success=True, halt_mode="exhausted",
                        raw={"prime_chain": [2, 3, 5, 7, 7]})
        assert MemoryOrderHysteresisScenario._prime_set(r) == frozenset({"2", "3", "5", "7"})

    def test_prime_set_none_on_failure(self):
        r = CycleResult(cycle_index=0, success=False, halt_mode="adapter_error", raw={})
        assert MemoryOrderHysteresisScenario._prime_set(r) is None

    def test_prime_set_fallback_to_rosetta(self):
        r = CycleResult(cycle_index=0, success=True, halt_mode="exhausted",
                        raw={"rosetta_primes": {"11": 1, "13": 1}})
        assert MemoryOrderHysteresisScenario._prime_set(r) == frozenset({"11", "13"})
