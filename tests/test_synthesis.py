"""Tests for the I pillar — Cumulative Meta-Analysis."""

import pytest

from ophamin.synthesis.cma import CumulativeMetaAnalysis


def test_fixed_effect_pooling_matches_hand_computation():
    cma = CumulativeMetaAnalysis(random_effects=False)
    cma.add(2.0, 1.0)
    result = cma.add(4.0, 1.0)
    # equal weights -> pooled = 3.0, variance = 1 / (1 + 1) = 0.5
    assert result.estimate == pytest.approx(3.0)
    assert result.variance == pytest.approx(0.5)


def test_confidence_interval_narrows_as_iterations_accumulate():
    cma = CumulativeMetaAnalysis(random_effects=False)
    widths = []
    for _ in range(6):
        widths.append(cma.add(1.0, 0.25).ci_width)
    # each additional identical study must tighten the interval
    assert all(widths[i] > widths[i + 1] for i in range(len(widths) - 1))


def test_homogeneous_studies_give_zero_between_study_variance():
    cma = CumulativeMetaAnalysis(random_effects=True)
    for _ in range(5):
        result = cma.add(1.0, 0.1)
    assert result.tau2 == pytest.approx(0.0, abs=1e-9)
    assert result.i_squared == pytest.approx(0.0, abs=1e-9)


def test_heterogeneous_studies_produce_positive_tau2_and_i2():
    cma = CumulativeMetaAnalysis(random_effects=True)
    for effect in (0.0, 1.0, 2.0, 3.0):
        result = cma.add(effect, 0.01)  # tight variances, spread effects
    assert result.tau2 > 0.0
    assert result.i_squared > 50.0


def test_first_significant_k_on_a_clearly_positive_series():
    cma = CumulativeMetaAnalysis(random_effects=False)
    for _ in range(4):
        cma.add(1.0, 0.04)  # se = 0.2, CI excludes 0 from the first study
    assert cma.first_significant_k() == 1


def test_first_significant_k_none_when_straddling_zero():
    cma = CumulativeMetaAnalysis(random_effects=False)
    for effect in (-1.0, 1.0, -1.0, 1.0):
        cma.add(effect, 1.0)
    # pooled estimate hovers around 0 — never lastingly significant
    assert cma.first_significant_k() is None


def test_two_stage_freezes_tau2_after_n():
    cma = CumulativeMetaAnalysis(random_effects=True, tau2_fixed_after=3)
    for effect in (0.0, 1.0, 2.0):
        cma.add(effect, 0.05)
    frozen = cma.result().tau2
    # later, very heterogeneous studies must not change the frozen tau^2
    cma.add(50.0, 0.05)
    assert cma.result().tau2 == pytest.approx(frozen)


def test_variance_must_be_positive():
    cma = CumulativeMetaAnalysis()
    with pytest.raises(ValueError):
        cma.add(1.0, 0.0)


def test_plot_writes_a_file(tmp_path):
    pytest.importorskip("matplotlib")
    cma = CumulativeMetaAnalysis(random_effects=False)
    for _ in range(5):
        cma.add(1.0, 0.1)
    out = cma.plot(str(tmp_path / "cma.png"))
    assert (tmp_path / "cma.png").exists()
    assert out.endswith("cma.png")
