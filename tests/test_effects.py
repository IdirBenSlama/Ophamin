"""Tests for the M pillar — mixed-effects and Multi-Experiment Analysis.

The strong assertions cross-check Ophamin's wrappers against the underlying
statsmodels models driven directly.
"""

import math
import warnings

import numpy as np
import pandas as pd
import pytest
import statsmodels.formula.api as smf
from statsmodels.regression.mixed_linear_model import MixedLM
from statsmodels.stats.anova import anova_lm

from ophamin.effects.mea import MultiExperimentAnalysis
from ophamin.effects.mixed_effects import RandomInterceptModel, center_and_scale


def _mixed_data(seed: int = 0, m: int = 40, n_per: int = 20):
    rng = np.random.default_rng(seed)
    u = rng.normal(0.0, math.sqrt(0.5), size=m)  # true sigma_u^2 = 0.5
    y, x, groups = [], [], []
    for i in range(m):
        xi = rng.normal(0.0, 1.0, size=n_per)
        ei = rng.normal(0.0, 1.0, size=n_per)  # true sigma_e^2 = 1.0
        yi = 2.0 + 1.5 * xi + u[i] + ei
        y.extend(yi.tolist())
        x.extend(xi.tolist())
        groups.extend([i] * n_per)
    return np.array(y), np.array(x), groups


def test_center_and_scale_normalises_and_skips_constants():
    X = np.column_stack([np.ones(50), np.linspace(10.0, 20.0, 50)])
    scaled, mean, std = center_and_scale(X)
    assert np.allclose(scaled[:, 0], 1.0)
    assert mean[0] == 0.0 and std[0] == 1.0
    assert abs(scaled[:, 1].mean()) < 1e-9
    assert abs(scaled[:, 1].std(ddof=0) - 1.0) < 1e-9


def test_random_intercept_matches_statsmodels_mixedlm_directly():
    y, x, groups = _mixed_data(seed=0)
    model = RandomInterceptModel().fit(
        y, x, groups, fit_intercept=True, feature_names=["x"]
    )
    X = np.column_stack([np.ones(len(y)), x])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ref = MixedLM(endog=y, exog=X, groups=groups).fit(reml=True)
    assert np.allclose(model.fixed_effects, np.asarray(ref.fe_params), rtol=1e-6)
    assert np.allclose(model.fixed_effects_se, np.asarray(ref.bse_fe), rtol=1e-6)
    assert model.sigma_e2 == pytest.approx(float(ref.scale), rel=1e-6)
    assert model.sigma_u2 == pytest.approx(float(np.asarray(ref.cov_re)[0, 0]), rel=1e-6)


def test_random_intercept_recovers_known_parameters_in_a_sane_range():
    y, x, groups = _mixed_data(seed=0)
    model = RandomInterceptModel().fit(
        y, x, groups, fit_intercept=True, feature_names=["x"]
    )
    assert model.converged
    assert model.feature_names == ["intercept", "x"]
    assert abs(model.fixed_effects[0] - 2.0) < 0.4   # intercept
    assert abs(model.fixed_effects[1] - 1.5) < 0.2   # slope
    assert 0.1 < model.sigma_u2 < 1.0                # true 0.5 (REML, noisy at m=40)
    assert 0.7 < model.sigma_e2 < 1.4                # true 1.0
    assert 0.05 < model.icc < 0.6


def test_random_intercept_model_needs_two_groups():
    with pytest.raises(ValueError):
        RandomInterceptModel().fit([1.0, 2.0], [[1.0], [1.0]], groups=["g", "g"])


def test_mea_marginal_effect_recovers_treatment_effect():
    rng = np.random.default_rng(0)
    n = 500
    treat = rng.integers(0, 2, size=n)
    outcome = 10.0 + 2.0 * treat + rng.normal(0.0, 1.0, size=n)
    mea = MultiExperimentAnalysis({"exp": treat.tolist()}, outcome.tolist())
    effects = mea.marginal_effect("exp", baseline=0)
    assert 1 in effects
    assert abs(effects[1].effect - 2.0) < 0.3
    assert effects[1].p_value < 1e-6


def test_mea_interaction_test_matches_statsmodels_anova():
    rng = np.random.default_rng(1)
    n = 600
    a = rng.integers(0, 2, size=n)
    b = rng.integers(0, 2, size=n)
    interacting = 10.0 + 2.0 * a + 3.0 * b + 5.0 * a * b + rng.normal(0.0, 1.0, size=n)
    mea = MultiExperimentAnalysis(
        {"a": a.tolist(), "b": b.tolist()}, interacting.tolist()
    )
    res = mea.interaction_test("a", "b")
    # cross-check against a direct statsmodels anova_lm on the same data
    df = pd.DataFrame({"outcome": interacting, "A": a.astype(str), "B": b.astype(str)})
    aov = anova_lm(smf.ols("outcome ~ C(A) * C(B)", data=df).fit(), typ=2)
    assert res.f_stat == pytest.approx(float(aov.loc["C(A):C(B)", "F"]), rel=1e-6)
    assert res.p_value == pytest.approx(float(aov.loc["C(A):C(B)", "PR(>F)"]), rel=1e-6)
    assert res.p_value < 1e-6  # the interaction is real


def test_mea_interaction_test_additive_is_not_significant():
    rng = np.random.default_rng(2)
    n = 600
    a = rng.integers(0, 2, size=n)
    b = rng.integers(0, 2, size=n)
    additive = 10.0 + 2.0 * a + 3.0 * b + rng.normal(0.0, 1.0, size=n)
    mea = MultiExperimentAnalysis({"a": a.tolist(), "b": b.tolist()}, additive.tolist())
    assert mea.interaction_test("a", "b").p_value > 0.05


def test_mea_conditional_effect_and_joint_estimate_run():
    rng = np.random.default_rng(3)
    n = 400
    a = rng.integers(0, 2, size=n)
    b = rng.integers(0, 2, size=n)
    outcome = 10.0 + 4.0 * a * b + rng.normal(0.0, 1.0, size=n)
    mea = MultiExperimentAnalysis({"a": a.tolist(), "b": b.tolist()}, outcome.tolist())

    within_b1 = mea.conditional_effect("a", given={"b": 1}, baseline=0)
    within_b0 = mea.conditional_effect("a", given={"b": 0}, baseline=0)
    assert within_b1[1].effect > within_b0[1].effect

    joint = mea.joint_estimate()
    assert 0.0 <= joint.r_squared <= 1.0
    assert joint.n_obs == n
    assert any(c.name == "Intercept" for c in joint.coefficients)  # statsmodels naming
