"""Tests for the O pillar — SPC control charts and SRM detection."""

import numpy as np
import pytest

from ophamin.measuring.pillars.observability.spc import (
    IndividualsChart,
    XbarRChart,
    western_electric_rules,
)
from ophamin.measuring.pillars.observability.srm import SRMDetector


def test_xbar_r_chart_reproduces_classic_constants():
    # at sigma_limit=3 the L-sigma limits must equal the textbook A2/D3/D4 limits.
    rng = np.random.default_rng(0)
    subgroups = rng.normal(10.0, 2.0, size=(60, 5))  # n = 5
    chart = XbarRChart(sigma_limit=3.0).fit(subgroups)

    lcl_x, center_x, ucl_x = chart.x_limits
    half = (ucl_x - lcl_x) / 2.0
    # A2 for n=5 is 0.577
    assert abs(half / chart.rbar - 0.577) < 0.005
    assert center_x == pytest.approx(chart.xbarbar)

    lcl_r, _, ucl_r = chart.r_limits
    # D4 for n=5 is 2.114, D3 is 0
    assert abs(ucl_r / chart.rbar - 2.114) < 0.01
    assert lcl_r == 0.0


def test_xbar_r_chart_flags_out_of_control_subgroup():
    rng = np.random.default_rng(1)
    stable = rng.normal(10.0, 1.0, size=(50, 5))
    chart = XbarRChart(sigma_limit=3.0).fit(stable)
    test = rng.normal(10.0, 1.0, size=(10, 5))
    test[4, :] += 20.0  # a blatantly shifted subgroup
    result = chart.evaluate(test)
    assert 4 in result.out_of_control


def test_individuals_chart_flags_spike():
    rng = np.random.default_rng(2)
    series = rng.normal(100.0, 3.0, size=80)
    chart = IndividualsChart(sigma_limit=3.0).fit(series)
    probe = series.copy()
    probe[40] += 60.0
    result = chart.evaluate(probe)
    assert 40 in result.out_of_control
    assert result.classify(40) == "special"


def test_western_electric_rule_1_single_point_beyond_3sigma():
    values = np.zeros(20)
    values[10] = 4.0  # 4 sigma out
    violations = western_electric_rules(values, center=0.0, sigma=1.0)
    assert any(v.rule == 1 and v.index == 10 for v in violations)


def test_western_electric_rule_4_eight_on_one_side():
    values = np.array([0.5] * 10)  # all above the centre line
    violations = western_electric_rules(values, center=0.0, sigma=1.0)
    assert any(v.rule == 4 for v in violations)


def test_srm_balanced_split_is_not_a_mismatch():
    detector = SRMDetector({"control": 0.5, "treatment": 0.5}, alpha=0.001)
    result = detector.check({"control": 5000, "treatment": 4980})
    assert not result.is_mismatch
    assert result.pvalue > 0.001


def test_srm_skewed_split_is_a_mismatch_with_known_chi2():
    detector = SRMDetector({"control": 0.5, "treatment": 0.5}, alpha=0.001)
    result = detector.check({"control": 600, "treatment": 400})
    # chi2 = (600-500)^2/500 + (400-500)^2/500 = 40
    assert result.chi2 == pytest.approx(40.0)
    assert result.is_mismatch
    assert result.pvalue < 1e-6


def test_srm_diagnose_localises_offending_segment():
    detector = SRMDetector({"control": 0.5, "treatment": 0.5}, alpha=0.001)
    offenders = detector.diagnose(
        {
            "chrome": {"control": 5000, "treatment": 5000},
            "safari": {"control": 900, "treatment": 100},  # broken here
        }
    )
    assert offenders
    assert offenders[0][0] == "safari"


def test_srm_rejects_unexpected_variant():
    detector = SRMDetector({"a": 0.5, "b": 0.5})
    with pytest.raises(ValueError):
        detector.check({"a": 10, "b": 10, "c": 10})


def test_srm_matches_scipy_chisquare_directly():
    from scipy import stats as scipy_stats

    detector = SRMDetector({"control": 0.5, "treatment": 0.5}, alpha=0.001)
    result = detector.check({"control": 5200, "treatment": 4800})
    ref = scipy_stats.chisquare(f_obs=[5200, 4800], f_exp=[5000, 5000])
    assert result.chi2 == pytest.approx(float(ref.statistic))
    assert result.pvalue == pytest.approx(float(ref.pvalue))


# -- SPC has no dominant Python library; validate against published references --

def test_control_chart_constants_match_published_table():
    """The fitted limits must reproduce Montgomery's published A2 / D3 / D4 table."""
    # subgroup size n -> (A2 for the X-bar chart, D3, D4 for the R chart)
    published = {
        2: (1.880, 0.0, 3.267),
        3: (1.023, 0.0, 2.574),
        4: (0.729, 0.0, 2.282),
        5: (0.577, 0.0, 2.114),
        6: (0.483, 0.0, 2.004),
        7: (0.419, 0.076, 1.924),
        8: (0.373, 0.136, 1.864),
        9: (0.337, 0.184, 1.816),
        10: (0.308, 0.223, 1.777),
    }
    rng = np.random.default_rng(0)
    for n, (a2, d3, d4) in published.items():
        subgroups = rng.normal(50.0, 5.0, size=(80, n))
        chart = XbarRChart(sigma_limit=3.0).fit(subgroups)
        lcl_x, center_x, ucl_x = chart.x_limits
        lcl_r, _, ucl_r = chart.r_limits
        assert (ucl_x - center_x) / chart.rbar == pytest.approx(a2, abs=0.01)
        assert ucl_r / chart.rbar == pytest.approx(d4, abs=0.01)
        assert lcl_r / chart.rbar == pytest.approx(d3, abs=0.01)


def test_western_electric_rules_2_and_3():
    # rule 2 — 2 of 3 consecutive points beyond 2 sigma, same side
    v2 = np.array([0.0, 2.5, 0.0, 2.5, 0.0])
    assert any(v.rule == 2 for v in western_electric_rules(v2, center=0.0, sigma=1.0))
    # rule 3 — 4 of 5 consecutive points beyond 1 sigma, same side
    v3 = np.array([1.5, 1.5, 1.5, 1.5, 1.5])
    assert any(v.rule == 3 for v in western_electric_rules(v3, center=0.0, sigma=1.0))
