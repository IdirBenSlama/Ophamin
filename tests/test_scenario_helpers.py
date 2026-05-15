"""Tests for the scenario-authoring helpers (Layer B foundation).

Pins each extractor against the shapes that the live Kimera substrate emits
*and* the synthetic shapes the unit tests use, so a future Kimera field-name
change is caught here first.
"""

from __future__ import annotations

import pytest

from ophamin.measuring.scenarios import helpers
from ophamin.seeing.substrate.base import CycleResult


def _result(*, raw=None, success=True, halt_mode="commit") -> CycleResult:
    return CycleResult(
        cycle_index=0, success=success, raw=raw or {}, halt_mode=halt_mode
    )


# -- gwf_cleared / gwf_allowed_directly ------------------------------------


def test_gwf_cleared_returns_true_on_cleared_verdict():
    r = _result(raw={"gwf_verdict": "cleared"})
    assert helpers.gwf_cleared(r)


def test_gwf_cleared_returns_false_on_blocked_verdict():
    r = _result(raw={"gwf_verdict": "blocked:CRITICAL threat"})
    assert not helpers.gwf_cleared(r)


def test_gwf_cleared_returns_false_on_lockdown():
    r = _result(raw={"gwf_verdict": "cleared", "gwf_lockdown": True})
    assert not helpers.gwf_cleared(r)


def test_gwf_cleared_returns_false_on_failed_cycle():
    r = _result(raw={"gwf_verdict": "cleared"}, success=False)
    assert not helpers.gwf_cleared(r)


def test_gwf_cleared_defaults_cleared_when_no_verdict_present():
    # synthetic substrates may not set gwf_verdict — they're cleared by default
    assert helpers.gwf_cleared(_result(raw={}))


def test_gwf_allowed_directly_reads_allowed_key():
    r = _result(raw={"allowed": True})
    assert helpers.gwf_allowed_directly(r) is True
    r = _result(raw={"allowed": False})
    assert helpers.gwf_allowed_directly(r) is False
    # absent → None
    assert helpers.gwf_allowed_directly(_result(raw={})) is None


# -- halt_mode normalisation -----------------------------------------------


def test_halt_mode_normalises():
    assert helpers.halt_mode(_result(halt_mode="EXHAUSTED")) == "exhausted"
    assert helpers.halt_mode(_result(halt_mode=" amplitude_death ")) == "amplitude_death"
    assert helpers.halt_mode(CycleResult(0, True, {}, None)) == ""


# -- manipulation / danger -------------------------------------------------


def test_manipulation_detected_and_danger_theory_gated():
    assert helpers.manipulation_detected(_result(raw={"manipulation_detected": True}))
    assert not helpers.manipulation_detected(_result(raw={"manipulation_detected": False}))
    assert not helpers.manipulation_detected(_result(raw={}))
    assert helpers.danger_theory_gated(_result(raw={"danger_theory_gated": True}))


# -- dissonance / pds / phi -------------------------------------------------


def test_dissonance_count_from_events_list():
    r = _result(raw={"dissonance_events": [1, 2, 3, 4, 5]})
    assert helpers.dissonance_count(r) == 5


def test_dissonance_count_from_event_count_int():
    r = _result(raw={"dissonance_event_count": 7})
    assert helpers.dissonance_count(r) == 7


def test_dissonance_count_from_zetetic_contradictions_fallback():
    r = _result(raw={"zetetic_contradictions": [1, 2]})
    assert helpers.dissonance_count(r) == 2


def test_dissonance_count_zero_on_missing():
    assert helpers.dissonance_count(_result(raw={})) == 0


def test_dissonance_count_zero_on_failed_cycle():
    r = _result(raw={"dissonance_events": [1, 2]}, success=False)
    assert helpers.dissonance_count(r) == 0


def test_productive_dissonance_score_scalar():
    r = _result(raw={"productive_dissonance_score": 0.45})
    assert helpers.productive_dissonance_score(r) == pytest.approx(0.45)
    # absent → 0.0
    assert helpers.productive_dissonance_score(_result(raw={})) == 0.0


def test_phi_value_search_order():
    assert helpers.phi_value(_result(raw={"phi_value": 0.5})) == pytest.approx(0.5)
    assert helpers.phi_value(_result(raw={"phi": 0.3})) == pytest.approx(0.3)
    assert helpers.phi_value(_result(raw={"iit_phi": 0.7})) == pytest.approx(0.7)
    # bad scalar → 0.0
    assert helpers.phi_value(_result(raw={"phi": "not-a-float"})) == 0.0


# -- rosetta extractors -----------------------------------------------------


def test_rosetta_canonical_reads_canonical_key():
    r = _result(raw={"canonical": "water"})
    assert helpers.rosetta_canonical(r) == "water"


def test_rosetta_canonical_fallback_keys():
    r = _result(raw={"canonical_form": "eau"})
    assert helpers.rosetta_canonical(r) == "eau"


def test_rosetta_canonical_none_on_missing():
    assert helpers.rosetta_canonical(_result(raw={})) is None


def test_rosetta_prime_from_nested_dict():
    r = _result(raw={"prime": {"composite": 506413, "p_thermo": 17, "p_identity": 29789}})
    assert helpers.rosetta_prime(r) == 506413


def test_rosetta_prime_from_scalar_top_level():
    assert helpers.rosetta_prime(_result(raw={"composite": 232453})) == 232453
    assert helpers.rosetta_prime(_result(raw={"prime": 17881})) == 17881


def test_rosetta_prime_none_on_bad_scalar():
    assert helpers.rosetta_prime(_result(raw={"composite": "not-int"})) is None


# -- adapter-error detection -----------------------------------------------


def test_is_adapter_error():
    assert helpers.is_adapter_error(
        CycleResult(0, False, {}, "adapter_error")
    )
    assert not helpers.is_adapter_error(_result(halt_mode="exhausted"))


# -- Wilson CI --------------------------------------------------------------


def test_wilson_95_ci_unanimous_success():
    lo, hi = helpers.wilson_95_ci(10, 10)
    assert lo > 0.6
    assert hi == pytest.approx(1.0)


def test_wilson_95_ci_zero_successes():
    lo, hi = helpers.wilson_95_ci(0, 20)
    assert lo == pytest.approx(0.0)
    assert hi < 0.2


def test_wilson_95_ci_empty_total():
    lo, hi = helpers.wilson_95_ci(0, 0)
    assert lo is None and hi is None


def test_wilson_95_ci_proportion_recovered():
    # 50 / 100 should give a CI that brackets 0.5
    lo, hi = helpers.wilson_95_ci(50, 100)
    assert lo < 0.5 < hi


# -- distribution stats ----------------------------------------------------


def test_distribution_stats_zero_shape_on_empty():
    s = helpers.distribution_stats([])
    assert s["n"] == 0
    assert s["min"] == 0.0
    assert s["max"] == 0.0


def test_distribution_stats_basic():
    s = helpers.distribution_stats([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    assert s["n"] == 10
    assert s["min"] == 1.0
    assert s["max"] == 10.0
    assert s["median"] == pytest.approx(5.5)
    assert s["mean"] == pytest.approx(5.5)
    # p10 / p90 should bracket the body of the distribution
    assert s["p10"] <= 2
    assert s["p90"] >= 9


def test_distribution_stats_single_value():
    s = helpers.distribution_stats([7])
    assert s["n"] == 1
    assert s["min"] == s["max"] == s["median"] == s["mean"] == 7.0


# -- inconclusive guards ----------------------------------------------------


def test_is_inconclusive_too_few_denominator():
    inc, reason = helpers.is_inconclusive(
        n_cycles=100, adapter_errors=0, n_denominator=5
    )
    assert inc
    assert "too few" in reason


def test_is_inconclusive_majority_adapter_errors():
    inc, reason = helpers.is_inconclusive(
        n_cycles=100, adapter_errors=60, n_denominator=20
    )
    assert inc
    assert "not exercised" in reason


def test_is_inconclusive_majority_adapter_errors_wins_over_denominator():
    inc, reason = helpers.is_inconclusive(
        n_cycles=100, adapter_errors=60, n_denominator=5
    )
    assert inc
    assert "not exercised" in reason  # not "too few"


def test_is_inconclusive_passes_when_solid():
    inc, reason = helpers.is_inconclusive(
        n_cycles=100, adapter_errors=2, n_denominator=50
    )
    assert not inc
    assert reason == ""
