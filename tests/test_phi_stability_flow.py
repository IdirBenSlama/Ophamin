"""Tests for the Phi-Stability Flow scenario (Ophamin's second FLOW-scope
proof). Exercises ``run()`` against a programmable fake adapter that returns
controllable per-cycle Φ — no live Kimera needed. Pins the LTL safety
invariant semantics:

  * all Φ above floor -> floor = min Φ -> VALIDATED, non-collapse rate 1.0
  * one Φ below floor -> REFUTED, worst cycle is the counterexample
  * a failed cycle is a gap (n_failed_cycles), not a 0.0 Φ
  * too few measured cycles -> INCONCLUSIVE
  * the proof emits the generic flow-evidence keys (flow_metric_label,
    flow_unit_label, flow_mean, worst_unit) the Console renders generically
  * a missing substrate is a loud failure
"""

from __future__ import annotations

import pytest

from ophamin.measuring.scenarios import PhiStabilityFlowScenario
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest


class _PhiAdapter(SubstrateUnderTest):
    """Fake adapter: returns a planned Φ per (stimulus, pass).

    ``plan`` maps stimulus_index -> list of per-pass Φ values, where each is
    a float, or ``None`` to simulate a failed cycle.
    """

    def __init__(self, stimuli, plan):
        self.name = "phi-fake"
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
        # plan entry: float -> real cycle (phi + concepts); None -> failed
        # cycle (no Φ); ("empty", float) -> empty-input cycle (Φ present but
        # no concept set — the degenerate-input case the refined invariant
        # excludes from the floor).
        out: list[CycleResult] = []
        for i, text in enumerate(stimuli):
            idx = self._stimuli.index(text)
            p = self._seen.get(idx, 0)
            self._seen[idx] = p + 1
            entry = self._plan[idx][p]
            if entry is None:
                out.append(CycleResult(
                    cycle_index=i, success=False, raw={},
                    halt_mode="adapter_error", error="planned-fail"))
            elif isinstance(entry, tuple) and entry[0] == "empty":
                out.append(CycleResult(
                    cycle_index=i, success=True, halt_mode="exhausted",
                    raw={"phi": entry[1], "concepts": []}))
            else:
                out.append(CycleResult(
                    cycle_index=i, success=True, halt_mode="exhausted",
                    raw={"phi": entry, "concepts": ["a", "b", "c"]}))
        return out


_STIM = ("alpha stimulus text", "beta stimulus text", "gamma stimulus text")


def _scenario(**kw):
    return PhiStabilityFlowScenario(
        stimuli=_STIM, n_passes=3, min_cycles=3, **kw)


class TestSchedule:
    def test_passes_over_stimuli(self):
        s = _scenario()
        sched = s.build_schedule()
        assert len(sched) == 9  # 3 passes x 3 stimuli
        assert [idx for idx, _ in sched] == [0, 1, 2, 0, 1, 2, 0, 1, 2]


class TestRunVerdict:
    def test_all_above_floor_validated(self):
        plan = {i: [0.7, 0.7, 0.7] for i in range(len(_STIM))}
        s = _scenario(phi_floor=0.05)
        rec = s.run(_PhiAdapter(_STIM, plan))
        assert rec.verdict.outcome == "VALIDATED"
        ev = rec.evidence[0]
        assert ev.statistic_name == "phi_floor"
        assert ev.statistic_value == pytest.approx(0.7)
        assert ev.detail["non_collapse_rate"] == 1.0
        assert ev.detail["n_failed_cycles"] == 0
        assert ev.detail["scope"] == "flow"
        # generic flow keys present for the Console.
        assert ev.detail["flow_metric_label"].startswith("Φ")
        assert ev.detail["flow_unit_label"] == "stimulus"
        assert ev.detail["flow_mean"] == pytest.approx(0.7)
        assert ev.detail["worst_unit"]["value"] == pytest.approx(0.7)

    def test_one_collapse_refuted(self):
        # gamma's 2nd pass collapses to 0.01 (below 0.05) -> REFUTED.
        plan = {
            0: [0.7, 0.7, 0.7],
            1: [0.7, 0.7, 0.7],
            2: [0.7, 0.01, 0.7],
        }
        s = _scenario(phi_floor=0.05)
        rec = s.run(_PhiAdapter(_STIM, plan))
        assert rec.verdict.outcome == "REFUTED"
        ev = rec.evidence[0]
        assert ev.statistic_value == pytest.approx(0.01)
        assert ev.detail["worst_unit"]["stimulus_index"] == 2
        assert ev.detail["non_collapse_rate"] < 1.0

    def test_failed_cycle_is_gap(self):
        plan = {
            0: [0.7, None, 0.7],
            1: [0.6, 0.6, 0.6],
            2: [0.65, 0.65, 0.65],
        }
        s = _scenario(phi_floor=0.05)
        rec = s.run(_PhiAdapter(_STIM, plan))
        ev = rec.evidence[0]
        assert ev.detail["n_failed_cycles"] == 1
        assert ev.detail["n_measured"] == 8
        assert rec.verdict.outcome == "VALIDATED"

    def test_too_few_inconclusive(self):
        plan = {
            0: [0.7, None, None],
            1: [None, None, None],
            2: [None, None, None],
        }
        s = PhiStabilityFlowScenario(stimuli=_STIM, n_passes=3, min_cycles=5)
        rec = s.run(_PhiAdapter(_STIM, plan))
        assert rec.verdict.outcome == "INCONCLUSIVE"

    def test_per_pass_mean_exposed(self):
        plan = {
            0: [0.8, 0.6, 0.4],
            1: [0.8, 0.6, 0.4],
            2: [0.8, 0.6, 0.4],
        }
        s = _scenario(phi_floor=0.05)
        rec = s.run(_PhiAdapter(_STIM, plan))
        pp = rec.evidence[0].detail["per_pass_mean"]
        assert pp["0"] == pytest.approx(0.8)
        assert pp["1"] == pytest.approx(0.6)
        assert pp["2"] == pytest.approx(0.4)

    def test_empty_input_cycle_excluded_from_floor(self):
        # Refined invariant: a cycle that produced no concept set has Φ=0 by
        # construction (nothing to integrate). It must NOT refute the floor —
        # it's counted as empty-input, and the over-all-cycles strict floor
        # records the 0.0 as a canary. This is the linux/cyber case.
        plan = {
            0: [0.7, ("empty", 0.0), 0.7],   # one degenerate cycle
            1: [0.7, 0.7, 0.7],
            2: [0.7, 0.7, 0.7],
        }
        s = _scenario(phi_floor=0.05)
        rec = s.run(_PhiAdapter(_STIM, plan))
        ev = rec.evidence[0]
        # Verdict holds on real-input cycles ...
        assert rec.verdict.outcome == "VALIDATED"
        assert ev.statistic_value == pytest.approx(0.7)
        # ... while the degeneracy is reported, not hidden.
        assert ev.detail["empty_input_cycles"] == 1
        assert ev.detail["empty_input_rate"] == pytest.approx(1 / 9)
        assert ev.detail["phi_floor_strict"] == pytest.approx(0.0)
        assert ev.detail["n_measured"] == 8        # real-input cycles
        assert ev.detail["n_returned"] == 9        # cycles that returned a Φ

    def test_all_empty_input_inconclusive(self):
        # If every cycle is degenerate, there are no real-input cycles to
        # decide on -> INCONCLUSIVE, not a false VALIDATED/REFUTED.
        plan = {i: [("empty", 0.0)] * 3 for i in range(len(_STIM))}
        s = _scenario(phi_floor=0.05)
        rec = s.run(_PhiAdapter(_STIM, plan))
        assert rec.verdict.outcome == "INCONCLUSIVE"
        assert rec.evidence[0].detail["empty_input_cycles"] == 9


class TestCrossCheck:
    """The CR1 statistical confirmation: Wilson CI on the non-collapse rate +
    a real-vs-empty Φ discrimination control. cross_check is one of
    passed/failed/skipped — never the old hardcoded n/a — and 'failed' means
    the control CONTRADICTS the claim, never just 'too few samples'.
    """

    def test_passes_via_discrimination(self):
        # 6 real cycles at Φ=0.7, 3 empty-input cycles at Φ=0.0 → complete
        # separation → Mann-Whitney p<0.05, real median > empty → discriminates
        # → cross_check passed even though n is small (the discrimination arm
        # confirms Φ is a responsive signal, not a constant).
        plan = {
            0: [0.7, 0.7, 0.7],
            1: [0.7, 0.7, 0.7],
            2: [("empty", 0.0), ("empty", 0.0), ("empty", 0.0)],
        }
        s = _scenario(phi_floor=0.05)
        rec = s.run(_PhiAdapter(_STIM, plan))
        ev = rec.evidence[0]
        assert rec.verdict.outcome == "VALIDATED"
        assert ev.cross_check == "passed"
        ctl = ev.detail["control"]
        assert ctl["phi_discriminates"] is True
        assert ctl["p_value"] is not None and ctl["p_value"] < 0.05
        assert ev.p_value == ctl["p_value"]
        assert ctl["real_median"] > ctl["empty_median"]

    def test_failed_on_real_collapse(self):
        # gamma's 2nd pass is a REAL-input cycle that collapses below floor →
        # the control agrees with the REFUTED verdict: cross_check failed.
        plan = {
            0: [0.7, 0.7, 0.7],
            1: [0.7, 0.7, 0.7],
            2: [0.7, 0.01, 0.7],
        }
        s = _scenario(phi_floor=0.05)
        rec = s.run(_PhiAdapter(_STIM, plan))
        ev = rec.evidence[0]
        assert rec.verdict.outcome == "REFUTED"
        assert ev.cross_check == "failed"
        assert ev.detail["control"]["non_collapse_rate"] < 1.0

    def test_skipped_when_underpowered(self):
        # 9 clean cycles, no empty arm: no collapse, but Wilson lower bound at
        # n=9 (~0.70) is below the 0.90 alive floor and there is no empty arm
        # to test discrimination → honestly 'skipped', NOT 'failed'.
        plan = {i: [0.7, 0.7, 0.7] for i in range(len(_STIM))}
        s = _scenario(phi_floor=0.05)
        rec = s.run(_PhiAdapter(_STIM, plan))
        ev = rec.evidence[0]
        assert rec.verdict.outcome == "VALIDATED"
        assert ev.cross_check == "skipped"
        ctl = ev.detail["control"]
        assert ctl["alive_confident"] is False
        assert ctl["ci_low"] is not None  # CI still computed + reported

    def test_passes_via_wilson_ci_at_scale(self):
        # 40 clean cycles (no empty arm): Wilson lower bound for 40/40 (~0.91)
        # clears the 0.90 alive floor → confidently alive → cross_check passed.
        stim = tuple(f"stimulus {i}" for i in range(8))
        plan = {i: [0.6] * 5 for i in range(len(stim))}
        s = PhiStabilityFlowScenario(
            stimuli=stim, n_passes=5, min_cycles=6, phi_floor=0.05)
        rec = s.run(_PhiAdapter(stim, plan))
        ev = rec.evidence[0]
        assert rec.verdict.outcome == "VALIDATED"
        assert ev.detail["n_measured"] == 40
        assert ev.cross_check == "passed"
        ctl = ev.detail["control"]
        assert ctl["alive_confident"] is True
        assert ctl["ci_low"] >= 0.90

    def test_crosscheck_in_reasoning(self):
        plan = {i: [0.6] * 5 for i in range(8)}
        stim = tuple(f"stimulus {i}" for i in range(8))
        s = PhiStabilityFlowScenario(
            stimuli=stim, n_passes=5, min_cycles=6, phi_floor=0.05)
        rec = s.run(_PhiAdapter(stim, plan))
        assert "cross-check" in rec.verdict.reasoning
        assert "Wilson" in rec.verdict.reasoning


class TestContract:
    def test_missing_substrate_raises(self):
        with pytest.raises(ValueError, match="live substrate"):
            _scenario().run(None)

    def test_registered_and_flow_scoped(self):
        from ophamin.measuring.scenarios import SCENARIOS
        assert "phi-stability-flow" in SCENARIOS
        s = _scenario()
        assert s.scope == "flow"
        assert s.family == "phi"
        assert s.tier.value == "scientific"

    def test_invalid_construction(self):
        with pytest.raises(ValueError):
            PhiStabilityFlowScenario(n_passes=0)
        with pytest.raises(ValueError):
            PhiStabilityFlowScenario(phi_floor=0.0)
        with pytest.raises(ValueError):
            PhiStabilityFlowScenario(stimuli=())

    def test_signed_proof_verifies(self):
        from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
        plan = {i: [0.7, 0.7, 0.7] for i in range(len(_STIM))}
        rec = _scenario().run(_PhiAdapter(_STIM, plan))
        assert rec.signature
        assert rec.verify_signature(DEFAULT_SIGN_KEY) is True
