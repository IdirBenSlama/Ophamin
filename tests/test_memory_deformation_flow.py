"""Tests for the Memory-as-Deformation Flow scenario (Ophamin's first
FLOW-scope proof).

The scenario fully overrides ``run()`` to drive a custom re-exposure
schedule, so these tests exercise ``run()`` against a programmable fake
adapter that returns controllable per-cycle concept sets — no live Kimera
needed. We pin the temporal-logic invariant semantics:

  * identical re-exposures -> floor 1.0 -> VALIDATED
  * one divergent re-exposure -> floor drops -> REFUTED (the LTL □ invariant
    is falsified by a single violating pair)
  * a failed exposure is a gap (n_failed), never a 0.0 Jaccard
  * too few valid pairs -> INCONCLUSIVE
  * the schedule spaces re-exposures by len(stimuli)
  * a missing substrate is a loud failure (flow needs a real trajectory)
"""

from __future__ import annotations

import pytest

from ophamin.measuring.scenarios import MemoryDeformationFlowScenario
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest


class _PlannedAdapter(SubstrateUnderTest):
    """Fake adapter: returns a planned concept set per (stimulus, exposure).

    ``plan`` maps stimulus_index -> list of per-exposure payloads, where
    each payload is either a list[str] of concepts, or ``None`` to simulate
    a failed cycle (success=False, no concepts).
    """

    def __init__(self, stimuli, plan):
        self.name = "planned-fake"
        self._stimuli = tuple(stimuli)
        self._plan = plan
        self._seen: dict[int, int] = {}

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
            idx = self._stimuli.index(text)
            exposure = self._seen.get(idx, 0)
            self._seen[idx] = exposure + 1
            payload = self._plan[idx][exposure]
            if payload is None:
                out.append(CycleResult(
                    cycle_index=i, success=False, raw={},
                    halt_mode="adapter_error", error="planned-fail",
                ))
            else:
                out.append(CycleResult(
                    cycle_index=i, success=True, halt_mode="exhausted",
                    raw={"concepts": list(payload)},
                ))
        return out


_STIM = ("alpha stimulus text", "beta stimulus text", "gamma stimulus text")


def _scenario(**kw):
    return MemoryDeformationFlowScenario(
        stimuli=_STIM, n_exposures=3, min_pairs=3, **kw
    )


class TestSchedule:
    def test_spacing_is_len_stimuli(self):
        s = _scenario()
        sched = s.build_schedule()
        assert len(sched) == 9  # 3 stimuli x 3 exposures
        # stimulus 0 appears at 0, 3, 6 — gap == len(stimuli)
        positions = [k for k, (idx, _) in enumerate(sched) if idx == 0]
        assert positions == [0, 3, 6]

    def test_n_cycles_matches_schedule(self):
        s = _scenario()
        assert s.n_cycles == len(s.build_schedule())


class TestRunVerdict:
    def test_identical_reexposures_validated(self):
        # Every exposure of every stimulus returns the same concepts.
        plan = {
            i: [["x", "y", "z"]] * 3 for i in range(len(_STIM))
        }
        s = _scenario()
        rec = s.run(_PlannedAdapter(_STIM, plan))
        assert rec.verdict.outcome == "VALIDATED"
        ev = rec.evidence[0]
        assert ev.statistic_name == "recognition_jaccard_floor"
        assert ev.statistic_value == 1.0
        assert ev.detail["n_failed_exposures"] == 0
        assert ev.detail["scope"] == "flow"
        assert rec.verdict.observed_value == 1.0

    def test_one_divergent_reexposure_refuted(self):
        # Stimulus 1's third exposure forgets everything (disjoint set) ->
        # that pair's Jaccard is 0.0 -> floor 0.0 -> REFUTED.
        plan = {
            0: [["x", "y", "z"]] * 3,
            1: [["a", "b", "c"], ["a", "b", "c"], ["p", "q", "r"]],
            2: [["m", "n", "o"]] * 3,
        }
        s = _scenario()
        rec = s.run(_PlannedAdapter(_STIM, plan))
        assert rec.verdict.outcome == "REFUTED"
        ev = rec.evidence[0]
        assert ev.statistic_value == 0.0
        worst = ev.detail["worst_pair"]
        assert worst["stimulus_index"] == 1
        assert worst["jaccard"] == 0.0

    def test_failed_exposure_is_gap_not_zero(self):
        # Stimulus 0 fails on its 2nd exposure -> only ONE valid pair remains
        # for it (exposures 0<->2), which are identical -> floor stays 1.0,
        # and the failure is counted as a gap, not a 0.0 Jaccard.
        plan = {
            0: [["x", "y"], None, ["x", "y"]],
            1: [["a", "b"]] * 3,
            2: [["m", "n"]] * 3,
        }
        s = _scenario()
        rec = s.run(_PlannedAdapter(_STIM, plan))
        ev = rec.evidence[0]
        assert ev.detail["n_failed_exposures"] == 1
        assert ev.statistic_value == 1.0
        assert rec.verdict.outcome == "VALIDATED"

    def test_too_few_pairs_inconclusive(self):
        # Only stimulus 0 yields any pair (others fail every exposure) ->
        # n_pairs (3) below min_pairs=10 -> INCONCLUSIVE.
        plan = {
            0: [["x"], ["x"], ["x"]],
            1: [None, None, None],
            2: [None, None, None],
        }
        s = MemoryDeformationFlowScenario(
            stimuli=_STIM, n_exposures=3, min_pairs=10,
        )
        rec = s.run(_PlannedAdapter(_STIM, plan))
        assert rec.verdict.outcome == "INCONCLUSIVE"

    def test_partial_overlap_jaccard(self):
        # exposures share 2 of 3 -> Jaccard 2/4 = 0.5 across each pair.
        plan = {
            0: [["x", "y", "z"], ["x", "y", "w"], ["x", "y", "z"]],
            1: [["a", "b"]] * 3,
            2: [["m", "n"]] * 3,
        }
        s = _scenario(recognition_floor=0.4)
        rec = s.run(_PlannedAdapter(_STIM, plan))
        ev = rec.evidence[0]
        # stimulus 0 worst pair shares {x,y} of {x,y,z,w} = 0.5
        assert ev.detail["per_stimulus_floor"]["0"] == pytest.approx(0.5)
        assert rec.verdict.outcome == "VALIDATED"  # 0.5 >= 0.4


class TestNegativeControl:
    """The cross-check: recognition is only credited when same-stimulus
    similarity is significantly ABOVE the cross-stimulus baseline. This is
    what rules out the 'all text looks alike' artifact."""

    def test_real_recognition_control_passes(self):
        # Each stimulus has its own distinct, stable concept set → same-
        # stimulus Jaccard 1.0, cross-stimulus 0.0 → significant.
        plan = {
            0: [["a", "b"]] * 3,
            1: [["c", "d"]] * 3,
            2: [["e", "f"]] * 3,
        }
        rec = _scenario().run(_PlannedAdapter(_STIM, plan))
        ev = rec.evidence[0]
        ctrl = ev.detail["control"]
        assert ctrl["status"] == "passed"
        assert ctrl["recognition_significant"] is True
        assert ctrl["same_median"] > ctrl["cross_median"]
        assert ev.cross_check == "passed"
        assert ev.p_value is not None and ev.p_value < 0.05

    def test_artifact_similarity_control_fails(self):
        # Every stimulus shares the SAME concept set → same-stimulus and
        # cross-stimulus are equally similar → recognition NOT above baseline.
        plan = {i: [["x", "y"]] * 3 for i in range(len(_STIM))}
        rec = _scenario(recognition_floor=0.5).run(_PlannedAdapter(_STIM, plan))
        ev = rec.evidence[0]
        ctrl = ev.detail["control"]
        # The LTL floor still validates (1.0 >= 0.5), but the control flags
        # that this "recognition" is indistinguishable from the baseline.
        assert ctrl["recognition_significant"] is False
        assert ev.cross_check in ("failed", "skipped")


class TestContract:
    def test_missing_substrate_raises(self):
        s = _scenario()
        with pytest.raises(ValueError, match="live substrate"):
            s.run(None)

    def test_registered_and_flow_scoped(self):
        from ophamin.measuring.scenarios import SCENARIOS
        assert "memory-deformation-flow" in SCENARIOS
        s = _scenario()
        assert s.scope == "flow"
        assert s.family == "memory"
        assert s.tier.value == "scientific"

    def test_invalid_construction(self):
        with pytest.raises(ValueError):
            MemoryDeformationFlowScenario(n_exposures=1)
        with pytest.raises(ValueError):
            MemoryDeformationFlowScenario(recognition_floor=1.5)
        with pytest.raises(ValueError):
            MemoryDeformationFlowScenario(stimuli=())

    def test_signed_proof_verifies(self):
        from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
        plan = {i: [["x", "y", "z"]] * 3 for i in range(len(_STIM))}
        s = _scenario()
        rec = s.run(_PlannedAdapter(_STIM, plan))
        assert rec.signature
        assert rec.verify_signature(DEFAULT_SIGN_KEY) is True

    def test_corpus_label_flows_into_evidence(self):
        # Default label, then a custom one (e.g. a real-corpus run).
        plan = {i: [["x", "y", "z"]] * 3 for i in range(len(_STIM))}
        default = _scenario().run(_PlannedAdapter(_STIM, plan))
        assert default.evidence[0].detail["flow_corpus_label"] == "kimera-genesis"

        labelled = MemoryDeformationFlowScenario(
            stimuli=_STIM, n_exposures=3, min_pairs=3,
            corpus_label="enron (real business email)",
        ).run(_PlannedAdapter(_STIM, plan))
        assert labelled.evidence[0].detail["flow_corpus_label"] == (
            "enron (real business email)"
        )
