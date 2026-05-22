"""Tests for the cued-recall memory proof — isolating memory from re-derivation.

A programmable fake adapter models the two worlds the proof must distinguish:

  * memory=True  — a partial cue of a SEEN item completes to the full concept
    set (recall ~1.0), while a never-seen cue yields only the fragment
    (~0.4) → memory_lift > 0 → VALIDATED.
  * memory=False — every cue yields only its fragment, seen or not → lift ~0
    → not VALIDATED (the determinism world the horizon proof couldn't exclude).
"""

from __future__ import annotations

import pytest

from ophamin.measuring.scenarios import SCENARIOS
from ophamin.measuring.scenarios.memory_cued_recall_flow import (
    MemoryCuedRecallFlowScenario,
)
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest


class _CuedAdapter(SubstrateUnderTest):
    """Word-set concepts. In memory mode a partial cue that is a word-prefix of
    a previously-seen full item completes to that full's words (pattern
    completion); otherwise it returns only the cue's own words."""

    def __init__(self, *, memory: bool = True):
        self.name = "cued-fake"
        self._seen: dict[str, bool] = {}
        self._memory = memory

    def git_commit(self) -> str:
        return "fakecommit01"

    def reset(self) -> None:
        self._seen = {}

    def metadata(self) -> dict:
        return {"name": self.name, "git_commit": self.git_commit()}

    def run_cycle(self, stimulus, params=None) -> CycleResult:  # pragma: no cover
        return self.run_batch([stimulus])[0]

    def run_batch(self, texts, params=None) -> list[CycleResult]:
        out: list[CycleResult] = []
        for i, t in enumerate(texts):
            words = t.split()
            completed = None
            if self._memory:
                for full in self._seen:
                    fw = full.split()
                    if len(words) < len(fw) and fw[: len(words)] == words:
                        completed = full
                        break
            if completed is not None:
                concepts = completed.split()        # memory completes the cue
            else:
                concepts = words                    # fragment / fresh full
                self._seen[t] = True
            out.append(CycleResult(
                cycle_index=i, success=True, halt_mode="exhausted",
                raw={"concepts": list(dict.fromkeys(concepts))}))
        return out


def _seen(n=20):
    return tuple(" ".join(f"sk{i}t{w}" for w in range(10)) for i in range(n))


def _control(n=12):
    return tuple(" ".join(f"ck{j}t{w}" for w in range(10)) for j in range(n))


def _scenario(**kw):
    kw.setdefault("stimuli", _seen(20))
    kw.setdefault("control_stimuli", _control(12))
    kw.setdefault("n_probes", 10)
    kw.setdefault("cue_fraction", 0.4)
    kw.setdefault("min_probes", 5)
    return MemoryCuedRecallFlowScenario(**kw)


class TestVerdict:
    def test_memory_world_validated(self):
        rec = _scenario().run(_CuedAdapter(memory=True))
        assert rec.verdict.outcome == "VALIDATED"
        ev = rec.evidence[0]
        assert ev.statistic_name == "memory_lift"
        assert ev.statistic_value > 0.3            # ~0.6 lift
        assert ev.detail["seen_recall_mean"] > ev.detail["control_recall_mean"]
        assert ev.cross_check == "passed"
        assert ev.p_value is not None and ev.p_value < 0.05

    def test_determinism_world_not_validated(self):
        rec = _scenario().run(_CuedAdapter(memory=False))
        # seen and control cues both yield only the fragment -> lift ~0
        assert rec.verdict.outcome != "VALIDATED"
        ev = rec.evidence[0]
        assert abs(ev.statistic_value) < 0.1
        assert ev.detail["control"]["significant"] is False

    def test_lift_is_seen_minus_control(self):
        rec = _scenario().run(_CuedAdapter(memory=True))
        d = rec.evidence[0].detail
        assert d["memory_lift"] == pytest.approx(
            d["seen_recall_mean"] - d["control_recall_mean"], abs=1e-9)


class TestSchedule:
    def test_phases(self):
        s = _scenario()
        from collections import Counter
        phases = Counter(p for _, p in s.build_schedule())
        assert phases["stream"] == 20
        assert phases["seen_cue"] == 10
        assert phases["control_cue"] == 10
        assert phases["control_full"] == 10

    def test_partial_cue_first_fraction(self):
        s = _scenario(cue_fraction=0.4)
        assert s._partial_cue("a b c d e f g h i j") == "a b c d"


class TestContract:
    def test_disjoint_control_enforced(self):
        shared = _seen(8)
        with pytest.raises(ValueError, match="disjoint"):
            MemoryCuedRecallFlowScenario(stimuli=shared, control_stimuli=shared[:2])

    def test_auto_split_control_when_absent(self):
        s = MemoryCuedRecallFlowScenario(stimuli=_seen(12))
        # tail split off as control; the two are disjoint + non-empty
        assert s.control_stimuli
        assert not (set(s.stimuli) & set(s.control_stimuli))

    def test_invalid_cue_fraction(self):
        with pytest.raises(ValueError):
            MemoryCuedRecallFlowScenario(stimuli=_seen(8), cue_fraction=0.0)
        with pytest.raises(ValueError):
            MemoryCuedRecallFlowScenario(stimuli=_seen(8), cue_fraction=1.0)

    def test_missing_substrate_raises(self):
        with pytest.raises(ValueError, match="live substrate"):
            _scenario().run(None)

    def test_registered_and_flow_scoped(self):
        assert "memory-cued-recall-flow" in SCENARIOS
        s = _scenario()
        assert s.scope == "flow"
        assert s.family == "memory"
        assert s.tier.value == "scientific"

    def test_signed_proof_verifies(self):
        from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
        rec = _scenario().run(_CuedAdapter(memory=True))
        assert rec.signature
        assert rec.verify_signature(DEFAULT_SIGN_KEY) is True

    def test_control_fields_present(self):
        rec = _scenario().run(_CuedAdapter(memory=True))
        ctl = rec.evidence[0].detail["control"]
        assert "seen_median" in ctl and "control_median" in ctl
        assert "p_value" in ctl
