"""Tests for the substrate-liveness scenario + its multi-corpus battery.

Liveness measures DYNAMICAL aliveness: of the numeric signals a substrate emits
in every cycle, how many actually vary with the stimulus (live) vs sit at a
frozen default (dead). The load-bearing units are the numeric-leaf flattener and
the always-on live/frozen classifier in ``score`` — both exercised here without a
live substrate, on hand-built cycle streams with known dynamics.
"""

from __future__ import annotations

import pytest

from ophamin.measuring.scenarios.substrate_liveness import (
    SubstrateLivenessScenario,
    _flatten_numeric,
)
from ophamin.measuring.scenarios.substrate_liveness_battery import (
    SubstrateLivenessBatteryScenario,
)
from ophamin.seeing.substrate.base import CycleResult


class TestFlattenNumeric:
    def test_nested_dicts_become_dotted_paths(self):
        raw = {"a": 1, "b": {"c": 2.5, "d": True}, "s": "x", "n": None, "lst": [1, 2]}
        assert _flatten_numeric(raw) == {"a": 1.0, "b.c": 2.5, "b.d": 1.0}

    def test_non_finite_values_are_skipped(self):
        raw = {"x": float("inf"), "y": float("nan"), "z": 3.0}
        assert _flatten_numeric(raw) == {"z": 3.0}


class TestSubstrateLivenessScore:
    @staticmethod
    def _cycles(dicts: list[dict[str, float]]) -> list[CycleResult]:
        return [CycleResult(cycle_index=i, success=True, raw=d) for i, d in enumerate(dicts)]

    def test_always_on_live_vs_frozen_classification(self):
        # 4 cycles: 'alive' varies, 'frozen' constant, 'sometimes' under-sampled
        # (present in one cycle only → excluded from the always-on spine).
        dicts = [
            {"alive": 1.0, "frozen": 7.0},
            {"alive": 2.0, "frozen": 7.0},
            {"alive": 3.0, "frozen": 7.0, "sometimes": 1.0},
            {"alive": 4.0, "frozen": 7.0},
        ]
        score = SubstrateLivenessScenario(liveness_floor=0.8, n_cycles=4).score(
            self._cycles(dicts), []
        )
        det = score.evidence[0].detail
        assert det["always_on_total"] == 2  # alive + frozen (sometimes excluded)
        assert det["always_on_live"] == 1
        assert det["always_on_frozen"] == 1
        assert score.observed_value == pytest.approx(0.5)
        assert det["frozen_worklist"] == ["frozen"]
        assert "sometimes" not in det["frozen_worklist"]

    def test_no_successful_cycles_is_inconclusive(self):
        score = SubstrateLivenessScenario().score(
            [CycleResult(cycle_index=0, success=False, raw={})], []
        )
        assert score.inconclusive

    def test_no_numeric_signals_is_inconclusive(self):
        score = SubstrateLivenessScenario().score(
            [CycleResult(cycle_index=0, success=True, raw={"label": "x"})], []
        )
        assert score.inconclusive

    def test_claim_threshold_is_liveness_rate(self):
        claim = SubstrateLivenessScenario(liveness_floor=0.8).build_claim()
        assert claim.threshold.metric == "liveness_rate"
        assert claim.threshold.comparator == ">="
        assert claim.threshold.value == 0.8

    def test_rejects_bad_floor(self):
        with pytest.raises(ValueError):
            SubstrateLivenessScenario(liveness_floor=0.0)


class TestSubstrateLivenessBattery:
    def test_metadata_combines_corpora(self):
        scn = SubstrateLivenessBatteryScenario(
            per_corpus_cycles=10, corpus_names=("a", "b")
        )
        assert scn.n_cycles == 20
        assert scn.corpus_name == "a+b"

    def test_claim_threshold_is_union_rate(self):
        claim = SubstrateLivenessBatteryScenario().build_claim()
        assert claim.threshold.metric == "liveness_rate_union"
        assert claim.threshold.value == 0.8

    def test_reuses_parent_classifier(self):
        # the battery scores the combined union with the parent's score()
        assert SubstrateLivenessBatteryScenario.score is SubstrateLivenessScenario.score

    def test_rejects_empty_corpus_names(self):
        with pytest.raises(ValueError):
            SubstrateLivenessBatteryScenario(corpus_names=())
