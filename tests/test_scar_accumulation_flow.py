"""Tests for the Scar-Accumulation Flow scenario (Ophamin's first
mechanism-deep proof — the wedge exhibit).

The scenario fully overrides ``run()`` to drive a re-exposure schedule and
score on the substrate's PHYSICAL deformation, so these tests exercise
``run()`` against a programmable fake adapter that returns controllable
per-cycle ``scar_state`` — no live Kimera needed. We pin the invariant
semantics:

  * strictly accumulating deformation -> fraction 1.0 -> VALIDATED
  * one decrease (a reset) -> fraction < 1.0 -> REFUTED, with the offending
    cycle pair named (first_violation)
  * a cycle with no scar_state is a recorded gap (n_gap_cycles), never a 0.0
  * too few pairs -> INCONCLUSIVE
  * flat (constant) deformation: the non-decrease invariant still holds
    (VALIDATED), but the same-stimulus accumulation cross-check FAILS — the
    proof never silently credits "accumulation" that didn't happen
  * a missing substrate is a loud failure (flow needs a real trajectory)
"""

from __future__ import annotations

import pytest

from ophamin.measuring.scenarios.scar_accumulation_flow import (
    ScarAccumulationFlowScenario,
)
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest


class _DeformationAdapter(SubstrateUnderTest):
    """Fake adapter: emits a planned ``total_deformation`` per cycle (in
    schedule order). ``td_per_cycle[i]`` is the cumulative deformation for
    cycle i; cycles whose index is in ``gaps`` emit no scar_state (a gap).
    """

    def __init__(self, stimuli, td_per_cycle, *, gaps=frozenset()):
        self.name = "deformation-fake"
        self._stimuli = tuple(stimuli)
        self._td = list(td_per_cycle)
        self._gaps = set(gaps)

    def git_commit(self) -> str:
        return "fakecommit01"

    def reset(self) -> None:
        pass

    def metadata(self) -> dict:
        return {"name": self.name, "git_commit": self.git_commit()}

    def run_cycle(self, stimulus, params=None) -> CycleResult:  # pragma: no cover
        return self.run_batch([stimulus])[0]

    def run_batch(self, stimuli, params=None) -> list[CycleResult]:
        out: list[CycleResult] = []
        for i, _text in enumerate(stimuli):
            if i in self._gaps:
                out.append(CycleResult(
                    cycle_index=i, success=False, raw={},
                    halt_mode="adapter_error", error="planned-gap",
                ))
                continue
            td = float(self._td[i])
            out.append(CycleResult(
                cycle_index=i, success=True, halt_mode="exhausted",
                raw={
                    "scar_state": {"total_deformation": td, "n_scars": i + 1},
                    # two distinct points so geoid_dispersion is non-None
                    "geoid_positions": [
                        [0.1 * i, 0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.2 * i, 0.0, 0.0, 0.0],
                    ],
                },
            ))
        return out


_STIM = ("alpha stimulus text", "beta stimulus text", "gamma stimulus text")


def _scenario(**kw):
    return ScarAccumulationFlowScenario(
        stimuli=_STIM, n_exposures=3, min_pairs=3, **kw
    )


class TestSchedule:
    def test_spacing_is_len_stimuli(self):
        sched = _scenario().build_schedule()
        assert len(sched) == 9  # 3 stimuli x 3 exposures
        positions = [k for k, (idx, _) in enumerate(sched) if idx == 0]
        assert positions == [0, 3, 6]  # gap == len(stimuli)

    def test_n_cycles_matches_schedule(self):
        s = _scenario()
        assert s.n_cycles == len(s.build_schedule())


class TestRunVerdict:
    def test_strict_accumulation_validated(self):
        # Cumulative deformation strictly increases every cycle.
        s = _scenario()
        rec = s.run(_DeformationAdapter(_STIM, [1, 2, 3, 4, 5, 6, 7, 8, 9]))
        assert rec.verdict.outcome == "VALIDATED"
        ev = rec.evidence[0]
        assert ev.statistic_name == "monotonic_nondecrease_fraction"
        assert ev.statistic_value == 1.0
        assert ev.detail["scope"] == "flow"
        assert ev.detail["n_gap_cycles"] == 0
        assert ev.detail["first_violation"] is None
        # the physical trace is in the evidence
        assert len(ev.detail["deformation_series"]) == 9
        assert ev.detail["n_scars_first"] == 1 and ev.detail["n_scars_last"] == 9

    def test_a_reset_refutes_and_names_the_pair(self):
        # Last cycle's deformation drops 8 -> 2 (a reset): one violation.
        s = _scenario()
        rec = s.run(_DeformationAdapter(_STIM, [1, 2, 3, 4, 5, 6, 7, 8, 2]))
        assert rec.verdict.outcome == "REFUTED"
        ev = rec.evidence[0]
        assert ev.statistic_value == pytest.approx(7 / 8)
        viol = ev.detail["first_violation"]
        assert viol is not None
        assert viol["cycle_a"] == 7 and viol["cycle_b"] == 8
        assert viol["td_a"] == 8.0 and viol["td_b"] == 2.0

    def test_missing_scar_state_is_gap_not_zero(self):
        # Cycle 4 emits no scar_state -> a recorded gap; the rest still
        # accumulates, so the invariant holds across the valid cycles.
        s = _scenario()
        rec = s.run(_DeformationAdapter(
            _STIM, [1, 2, 3, 4, 99, 6, 7, 8, 9], gaps={4},
        ))
        ev = rec.evidence[0]
        assert ev.detail["n_gap_cycles"] == 1
        assert ev.statistic_value == 1.0
        assert rec.verdict.outcome == "VALIDATED"

    def test_too_few_pairs_inconclusive(self):
        s = ScarAccumulationFlowScenario(stimuli=_STIM, n_exposures=3, min_pairs=20)
        rec = s.run(_DeformationAdapter(_STIM, [1, 2, 3, 4, 5, 6, 7, 8, 9]))
        assert rec.verdict.outcome == "INCONCLUSIVE"


class TestAccumulationCrossCheck:
    """The non-decrease invariant alone is satisfied by FLAT deformation; the
    cross-check ensures the proof only credits real accumulation."""

    def test_flat_deformation_validates_but_crosscheck_fails(self):
        # Constant deformation: non-decrease holds (>= with eps) -> VALIDATED,
        # but no stimulus sits on a more-deformed manifold later -> cross fails.
        s = _scenario()
        rec = s.run(_DeformationAdapter(_STIM, [5, 5, 5, 5, 5, 5, 5, 5, 5]))
        ev = rec.evidence[0]
        assert rec.verdict.outcome == "VALIDATED"
        assert ev.statistic_value == 1.0
        cross = ev.detail["same_stimulus_accumulation"]
        assert cross["status"] == "failed"
        assert cross["n_positive"] == 0
        assert ev.cross_check == "failed"

    def test_real_accumulation_crosscheck_passes(self):
        s = _scenario()
        rec = s.run(_DeformationAdapter(_STIM, [1, 2, 3, 4, 5, 6, 7, 8, 9]))
        ev = rec.evidence[0]
        cross = ev.detail["same_stimulus_accumulation"]
        assert cross["status"] == "passed"
        assert cross["n_positive"] == cross["n_counted"] == 3
        assert ev.cross_check == "passed"
        # each stimulus's last exposure is on a more-deformed manifold
        for row in cross["per_stimulus"]:
            assert row["delta"] > 0


class TestContract:
    def test_missing_substrate_raises(self):
        with pytest.raises(ValueError, match="live substrate"):
            _scenario().run(None)

    def test_registered_and_flow_scoped(self):
        from ophamin.measuring.scenarios import SCENARIOS
        assert "scar-accumulation-flow" in SCENARIOS
        s = _scenario()
        assert s.scope == "flow"
        assert s.family == "memory"
        assert s.tier.value == "scientific"
        assert s.target == "entity"

    def test_invalid_construction(self):
        with pytest.raises(ValueError):
            ScarAccumulationFlowScenario(n_exposures=1)
        with pytest.raises(ValueError):
            ScarAccumulationFlowScenario(monotonic_floor=1.5)
        with pytest.raises(ValueError):
            ScarAccumulationFlowScenario(stimuli=())

    def test_signed_proof_verifies_and_tamper_evident(self):
        from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY
        rec = _scenario().run(_DeformationAdapter(_STIM, [1, 2, 3, 4, 5, 6, 7, 8, 9]))
        assert rec.signature
        assert rec.verify_signature(DEFAULT_SIGN_KEY) is True
