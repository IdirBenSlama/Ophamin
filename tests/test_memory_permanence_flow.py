"""Tests for the memory-permanence proof — memory in the scars/S4 manifold.

A programmable fake adapter models the three worlds the proof must distinguish,
emitting the REAL OrchestratorResult field names (``vault_stats``,
``arachne_web_coupling_frobenius``, ``alexandria_knowledge_mass_cumulative``,
``phi``, ``halt_reason``, ``concepts``) verified on live Kimera 2026-05-22:

  * ``mode="memory"``     — permanent scars accumulate (+1/cycle), the manifold
    coupling deepens, concepts are deterministic per stimulus (recognition
    stable). A re-exposed, recognised probe lands on strictly more scars every
    time → memory_path_dependence = 1.0 → VALIDATED.
  * ``mode="stateless"``  — the substrate RECOGNISES (deterministic concepts)
    but NEVER accumulates (scars constant). Δscars = 0 at every re-exposure →
    memory_path_dependence = 0.0 → REFUTED. This is the re-derivation world the
    concept-set proofs could not exclude.
  * ``mode="amnesia"``    — scars accumulate then RESET mid-run. The whole-run
    monotonicity is violated ("a scar cannot be reset" broke) → observed forced
    to 0.0 → REFUTED.
"""

from __future__ import annotations

import pytest

from ophamin.measuring.scenarios import SCENARIOS
from ophamin.measuring.scenarios.memory_permanence_flow import (
    MemoryPermanenceFlowScenario,
    _as_finite_float,
)
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest


class _PermanenceAdapter(SubstrateUnderTest):
    """Emits the real memory-substrate fields. ``mode`` selects the world."""

    def __init__(self, *, mode: str = "memory") -> None:
        self.name = "perm-fake"
        self._mode = mode
        self.reset()

    def git_commit(self) -> str:
        return "fakecommit01"

    def reset(self) -> None:
        self._cycle = 0
        self._scars = 0
        self._coupling = 1.0
        self._mass = 5.0
        self._seen: set[str] = set()

    def metadata(self) -> dict:
        return {"name": self.name, "git_commit": self.git_commit()}

    def run_cycle(self, stimulus, params=None) -> CycleResult:  # pragma: no cover
        return self.run_batch([stimulus])[0]

    def run_batch(self, texts, params=None) -> list[CycleResult]:
        out: list[CycleResult] = []
        n = len(texts)
        reset_at = n // 2
        for i, t in enumerate(texts):
            self._cycle += 1
            if self._mode == "memory":
                self._scars += 1
                self._coupling += 0.05
                self._mass += 3.0
            elif self._mode == "stateless":
                # recognises but never accumulates — the re-derivation world
                self._scars = 1
                self._coupling = 1.0
                self._mass = 5.0
            elif self._mode == "amnesia":
                self._scars += 1
                self._coupling += 0.05
                self._mass += 3.0
                if i == reset_at:
                    self._scars = 0  # a scar was reset — permanence broken
            else:  # pragma: no cover
                raise ValueError(f"unknown mode {self._mode!r}")

            # deterministic concepts from the stimulus → recognition is stable
            words = t.split()
            concepts = list(dict.fromkeys(
                w.strip(".,;:").lower() for w in words[:6] if w
            ))
            # first encounter halts one way, re-exposure another (path-dependence
            # at the cognitive layer — a characterisation, not the verdict)
            first = t not in self._seen
            self._seen.add(t)
            halt = "amplitude_death" if first else "exhausted"
            out.append(CycleResult(
                cycle_index=i, success=True, halt_mode=halt,
                raw={
                    "concepts": concepts,
                    "vault_stats": {
                        "total_scars_stored": self._scars,
                        "vault_a": {"scar_count": self._scars},
                        "vault_b": {"scar_count": 0},
                    },
                    "arachne_web_coupling_frobenius": self._coupling,
                    "alexandria_knowledge_mass_cumulative": self._mass,
                    "phi": 0.70,  # rigid Φ → memory is in the scars, not Φ
                    "halt_reason": halt,
                },
            ))
        return out


def _stimuli(n: int = 4) -> tuple[str, ...]:
    # ≥6 words each, distinguished by the index token so same-stimulus
    # recognition is 1.0 and cross-stimulus differs.
    return tuple(
        f"probe number {i} carries meaning {i} and structure {i}"
        for i in range(n)
    )


def _scenario(**kw) -> MemoryPermanenceFlowScenario:
    kw.setdefault("stimuli", _stimuli(4))
    kw.setdefault("n_exposures", 3)
    kw.setdefault("recognition_floor", 0.80)
    kw.setdefault("min_transitions", 4)
    return MemoryPermanenceFlowScenario(**kw)


class TestVerdict:
    def test_memory_world_validated(self):
        rec = _scenario().run(_PermanenceAdapter(mode="memory"))
        assert rec.verdict.outcome == "VALIDATED"
        ev = rec.evidence[0]
        assert ev.statistic_name == "memory_path_dependence"
        assert ev.statistic_value == pytest.approx(1.0)
        d = ev.detail
        assert d["permanence_holds"] is True
        assert d["scar_monotonicity_violations"] == []
        assert d["n_confirmed_transitions"] == d["n_recognised_transitions"]
        # the cross-check confirms scars deepen with exposure ordinal
        assert ev.cross_check == "passed"
        assert ev.p_value is not None and ev.p_value < 0.05

    def test_stateless_rederivation_refuted(self):
        # recognises perfectly but never accumulates → not memory
        rec = _scenario().run(_PermanenceAdapter(mode="stateless"))
        assert rec.verdict.outcome != "VALIDATED"
        ev = rec.evidence[0]
        assert ev.statistic_value == pytest.approx(0.0)
        d = ev.detail
        # permanence not violated (flat, non-decreasing) — it's the
        # NO-ACCUMULATION that refutes, not a reset
        assert d["permanence_holds"] is True
        assert d["memory_path_dependence"] == pytest.approx(0.0)
        # recognition still held (same-probe), proving the failure is memory,
        # not recognition
        assert d["recognition_floor_observed"] >= 0.80

    def test_amnesia_scar_reset_refuted(self):
        rec = _scenario().run(_PermanenceAdapter(mode="amnesia"))
        assert rec.verdict.outcome != "VALIDATED"
        ev = rec.evidence[0]
        d = ev.detail
        assert d["permanence_holds"] is False
        assert len(d["scar_monotonicity_violations"]) >= 1
        # a scar reset forces the honest observed value to 0.0
        assert ev.statistic_value == pytest.approx(0.0)

    def test_observed_is_confirmed_over_recognised(self):
        rec = _scenario().run(_PermanenceAdapter(mode="memory"))
        d = rec.evidence[0].detail
        assert d["memory_path_dependence"] == pytest.approx(
            d["n_confirmed_transitions"] / d["n_recognised_transitions"]
        )

    def test_accumulation_reported(self):
        rec = _scenario().run(_PermanenceAdapter(mode="memory"))
        acc = rec.evidence[0].detail["accumulation"]
        # scars grew over the run; the manifold coupling deepened
        assert acc["total_scars_stored"]["delta"] > 0
        assert acc["arachne_web_coupling_frobenius"]["delta"] > 0
        assert acc["alexandria_knowledge_mass_cumulative"]["delta"] > 0

    def test_phi_rigidity_characterised(self):
        # Φ is rigid in the fake (and on the live probe) → the proof must NOT
        # rely on Φ drift; it reports it as a characterisation only
        rec = _scenario().run(_PermanenceAdapter(mode="memory"))
        d = rec.evidence[0].detail
        assert d["phi_delta_abs_mean"] == pytest.approx(0.0)
        assert rec.verdict.outcome == "VALIDATED"  # validated despite Φ rigidity


class TestSchedule:
    def test_phases(self):
        s = _scenario()
        sched = s.build_schedule()
        assert len(sched) == 4 * 3
        # each stimulus appears n_exposures times
        from collections import Counter
        counts = Counter(idx for idx, _ in sched)
        assert all(c == 3 for c in counts.values())
        assert set(counts) == {0, 1, 2, 3}

    def test_interleave_gap(self):
        s = _scenario()
        sched = s.build_schedule()
        # stimulus 0 appears at cycles 0, 4, 8 (gap = len(stimuli))
        zero_cycles = [i for i, (idx, _) in enumerate(sched) if idx == 0]
        assert zero_cycles == [0, 4, 8]


class TestExtraction:
    def test_scar_count_prefers_total_scars_stored(self):
        r = CycleResult(cycle_index=0, success=True, halt_mode="exhausted",
                        raw={"vault_stats": {"total_scars_stored": 7,
                                             "vault_a": {"scar_count": 3},
                                             "vault_b": {"scar_count": 2}}})
        assert MemoryPermanenceFlowScenario._scar_count(r) == 7

    def test_scar_count_falls_back_to_vault_sum(self):
        r = CycleResult(cycle_index=0, success=True, halt_mode="exhausted",
                        raw={"vault_stats": {"vault_a": {"scar_count": 3},
                                             "vault_b": {"scar_count": 2}}})
        assert MemoryPermanenceFlowScenario._scar_count(r) == 5

    def test_scar_count_none_on_failure(self):
        r = CycleResult(cycle_index=0, success=False, halt_mode="adapter_error",
                        raw={})
        assert MemoryPermanenceFlowScenario._scar_count(r) is None

    def test_as_finite_float_rejects_non_finite_strings(self):
        # the Kimera runner serialises NaN/Inf as strings — must be treated absent
        assert _as_finite_float("nan") is None
        assert _as_finite_float("inf") is None
        assert _as_finite_float("1.5") == pytest.approx(1.5)
        assert _as_finite_float(2) == pytest.approx(2.0)
        assert _as_finite_float(True) is None


class TestContract:
    def test_registered_and_flow_scoped(self):
        assert "memory-permanence-flow" in SCENARIOS
        s = _scenario()
        assert s.scope == "flow"
        assert s.family == "memory"
        assert s.tier.value == "scientific"

    def test_invalid_n_exposures(self):
        with pytest.raises(ValueError):
            MemoryPermanenceFlowScenario(n_exposures=1)

    def test_invalid_recognition_floor(self):
        with pytest.raises(ValueError):
            MemoryPermanenceFlowScenario(recognition_floor=0.0)
        with pytest.raises(ValueError):
            MemoryPermanenceFlowScenario(recognition_floor=1.5)

    def test_missing_substrate_raises(self):
        with pytest.raises(ValueError, match="live substrate"):
            _scenario().run(None)

    def test_inconclusive_when_too_few_transitions(self):
        # 2 stimuli × 2 exposures = 2 transitions < min_transitions(4)
        s = MemoryPermanenceFlowScenario(
            stimuli=_stimuli(2), n_exposures=2, min_transitions=4,
        )
        rec = s.run(_PermanenceAdapter(mode="memory"))
        assert rec.verdict.outcome == "INCONCLUSIVE"

    def test_signed_proof_verifies(self):
        from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
        rec = _scenario().run(_PermanenceAdapter(mode="memory"))
        assert rec.signature
        assert rec.verify_signature(DEFAULT_SIGN_KEY) is True
