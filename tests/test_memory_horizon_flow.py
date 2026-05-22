"""Tests for the Memory-Horizon Flow scenario.

Exercises the recall-vs-lag machinery against a programmable fake adapter
(no live Kimera). Pins: the stream+probe schedule, the lag/beyond-window
partition, the verdict on perfect recall vs forgetting, the negative control,
INCONCLUSIVE on too-few beyond-window probes, and the generic flow keys.
"""

from __future__ import annotations

import pytest

from ophamin.measuring.scenarios import SCENARIOS
from ophamin.measuring.scenarios.memory_horizon_flow import (
    MemoryHorizonFlowScenario,
)
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest


class _HorizonAdapter(SubstrateUnderTest):
    """Returns item-specific concepts; on a re-probe (2nd time a text is seen)
    returns either the same set (perfect recall) or a degraded/disjoint set
    (forgetting), controlled by ``probe_recall``."""

    def __init__(self, stimuli, *, probe_recall: float = 1.0):
        self.name = "horizon-fake"
        self._stimuli = tuple(stimuli)
        self._seen: dict[str, int] = {}
        self._probe_recall = probe_recall

    def git_commit(self) -> str:
        return "fakecommit01"

    def reset(self) -> None:
        self._seen = {}

    def metadata(self) -> dict:
        return {"name": self.name, "git_commit": self.git_commit()}

    def run_cycle(self, stimulus, params=None) -> CycleResult:  # pragma: no cover
        return self.run_batch([stimulus])[0]

    def run_batch(self, stimuli, params=None) -> list[CycleResult]:
        out: list[CycleResult] = []
        for i, text in enumerate(stimuli):
            n = self._seen.get(text, 0)
            self._seen[text] = n + 1
            base = [f"{text}_a", f"{text}_b", f"{text}_c"]
            if n == 0:
                concepts = base                      # first exposure
            elif self._probe_recall >= 1.0:
                concepts = base                      # perfect recall
            elif self._probe_recall <= 0.0:
                concepts = [f"{text}_x", f"{text}_y"]  # disjoint -> recall 0
            else:
                keep = max(1, int(len(base) * self._probe_recall))
                concepts = base[:keep]
            out.append(CycleResult(
                cycle_index=i, success=True, halt_mode="exhausted",
                raw={"concepts": concepts}))
        return out


def _stim(n=12):
    return tuple(f"item {i} unique stream text" for i in range(n))


def _scenario(**kw):
    kw.setdefault("stimuli", _stim(12))
    kw.setdefault("n_probes", 6)
    kw.setdefault("window_ref", 3)
    kw.setdefault("recall_floor", 0.5)
    kw.setdefault("min_beyond_window", 3)
    return MemoryHorizonFlowScenario(**kw)


class TestSchedule:
    def test_stream_then_probe(self):
        s = _scenario()
        sched = s.build_schedule()
        assert len(sched) == 18  # 12 stream + 6 probe
        assert all(p == "stream" for *_, p in sched[:12])
        assert all(p == "probe" for *_, p in sched[12:])

    def test_probe_positions_spread_oldest_first(self):
        s = _scenario()
        pos = s._probe_positions()
        assert pos[0] == 0 and pos[-1] == 11
        assert pos == sorted(pos)  # oldest-first


class TestVerdict:
    def test_perfect_recall_validated(self):
        s = _scenario()
        rec = s.run(_HorizonAdapter(_stim(12), probe_recall=1.0))
        assert rec.verdict.outcome == "VALIDATED"
        ev = rec.evidence[0]
        assert ev.statistic_name == "recall_floor_beyond_window"
        assert ev.statistic_value == pytest.approx(1.0)
        assert ev.detail["n_beyond_window"] >= 3
        assert ev.detail["memory_horizon"] >= s.window_ref

    def test_forgetting_refuted(self):
        s = _scenario()
        rec = s.run(_HorizonAdapter(_stim(12), probe_recall=0.0))
        assert rec.verdict.outcome == "REFUTED"
        assert rec.evidence[0].statistic_value == pytest.approx(0.0)

    def test_lag_curve_and_beyond_partition(self):
        s = _scenario()
        rec = s.run(_HorizonAdapter(_stim(12), probe_recall=1.0))
        curve = rec.evidence[0].detail["lag_curve"]
        assert len(curve) == 6
        for p in curve:
            assert p["beyond_window"] == (p["lag"] > s.window_ref)
            assert p["probe_cycle"] >= 12  # probes are in the probe phase
            assert p["lag"] == p["probe_cycle"] - p["exposure_cycle"]
        # oldest item (position 0) carries the largest lag
        oldest = next(p for p in curve if p["stimulus_index"] == 0)
        assert oldest["lag"] == max(p["lag"] for p in curve)

    def test_inconclusive_when_window_ref_too_large(self):
        # window_ref beyond every probe's lag -> no beyond-window probes.
        s = _scenario(window_ref=9999)
        rec = s.run(_HorizonAdapter(_stim(12), probe_recall=1.0))
        assert rec.verdict.outcome == "INCONCLUSIVE"
        assert rec.evidence[0].detail["n_beyond_window"] == 0


class TestControl:
    def test_recall_significant_over_cross_item(self):
        # perfect recall on distinct items: beyond-window recall ~1.0, cross-
        # item Jaccard ~0 -> control passes (recall is real, not coincidence).
        s = _scenario()
        rec = s.run(_HorizonAdapter(_stim(12), probe_recall=1.0))
        ev = rec.evidence[0]
        assert ev.cross_check == "passed"
        ctl = ev.detail["control"]
        assert ctl["beyond_median"] > ctl["cross_median"]
        assert ev.p_value is not None and ev.p_value < 0.05


class TestContract:
    def test_registered_and_flow_scoped(self):
        assert "memory-horizon-flow" in SCENARIOS
        s = _scenario()
        assert s.scope == "flow"
        assert s.family == "memory"
        assert s.tier.value == "scientific"

    def test_missing_substrate_raises(self):
        with pytest.raises(ValueError, match="live substrate"):
            _scenario().run(None)

    def test_invalid_construction(self):
        with pytest.raises(ValueError):
            MemoryHorizonFlowScenario(stimuli=())
        with pytest.raises(ValueError):
            MemoryHorizonFlowScenario(n_probes=1)
        with pytest.raises(ValueError):
            MemoryHorizonFlowScenario(recall_floor=0.0)

    def test_generic_flow_keys_present(self):
        rec = _scenario().run(_HorizonAdapter(_stim(12), probe_recall=1.0))
        d = rec.evidence[0].detail
        assert d["flow_metric_label"].startswith("recall")
        assert d["flow_unit_label"] == "lag"
        assert "flow_mean" in d and "worst_unit" in d

    def test_signed_proof_verifies(self):
        from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
        rec = _scenario().run(_HorizonAdapter(_stim(12), probe_recall=1.0))
        assert rec.signature
        assert rec.verify_signature(DEFAULT_SIGN_KEY) is True
