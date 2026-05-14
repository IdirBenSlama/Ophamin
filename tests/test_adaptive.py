"""Tests for the A pillar — SPRT and the mixture SPRT."""

import math

import numpy as np
import pytest

from ophamin.adaptive.sprt import (
    ACCEPT_H0,
    ACCEPT_H1,
    BernoulliSPRT,
    GaussianSPRT,
    MixtureSPRT,
)


def test_sprt_boundaries_match_wald_formula():
    sprt = GaussianSPRT(mu0=0.0, mu1=1.0, sigma=1.0, alpha=0.05, beta=0.20)
    assert sprt.upper == math.log((1 - 0.20) / 0.05)
    assert sprt.lower == math.log(0.20 / (1 - 0.05))


def test_gaussian_sprt_accepts_h1_under_h1_data():
    sprt = GaussianSPRT(mu0=0.0, mu1=1.0, sigma=1.0, alpha=0.05, beta=0.05)
    rng = np.random.default_rng(0)
    decision = sprt.update_many(rng.normal(1.0, 1.0, size=500))
    assert decision == ACCEPT_H1


def test_gaussian_sprt_accepts_h0_under_h0_data():
    sprt = GaussianSPRT(mu0=0.0, mu1=1.0, sigma=1.0, alpha=0.05, beta=0.05)
    rng = np.random.default_rng(1)
    decision = sprt.update_many(rng.normal(0.0, 1.0, size=500))
    assert decision == ACCEPT_H0


def test_bernoulli_sprt_detects_high_rate():
    sprt = BernoulliSPRT(p0=0.5, p1=0.85, alpha=0.05, beta=0.05)
    rng = np.random.default_rng(2)
    decision = sprt.update_many(rng.binomial(1, 0.85, size=400))
    assert decision == ACCEPT_H1


def test_msprt_always_valid_pvalue_is_monotone_non_increasing():
    msprt = MixtureSPRT(mu0=0.0, sigma=1.0, tau2=1.0)
    rng = np.random.default_rng(3)
    last = 1.0
    for x in rng.normal(0.4, 1.0, size=200):
        p = msprt.update(float(x))
        assert p <= last + 1e-12
        last = p


def test_msprt_rejects_h0_under_a_real_shift():
    msprt = MixtureSPRT(mu0=0.0, sigma=1.0, tau2=1.0)
    rng = np.random.default_rng(4)
    msprt.update_many(rng.normal(0.6, 1.0, size=300))
    assert msprt.always_valid_pvalue < 0.05
    assert msprt.decision(alpha=0.05) == "reject_h0"


def test_msprt_stays_calm_under_h0():
    # under the null the anytime p-value should usually NOT cross 0.05;
    # checked across several seeds (the guarantee is probabilistic, <= 5%).
    crossings = 0
    for seed in range(20):
        msprt = MixtureSPRT(mu0=0.0, sigma=1.0, tau2=1.0)
        rng = np.random.default_rng(100 + seed)
        msprt.update_many(rng.normal(0.0, 1.0, size=300))
        if msprt.always_valid_pvalue < 0.05:
            crossings += 1
    assert crossings <= 3  # comfortably within the anytime-valid bound


def test_msprt_reset_clears_state():
    msprt = MixtureSPRT(mu0=0.0, sigma=1.0, tau2=1.0)
    msprt.update_many([5.0, 5.0, 5.0])
    msprt.reset()
    assert msprt.n == 0
    assert msprt.always_valid_pvalue == 1.0


# -- SPRT / mSPRT have no dominant Python library; validate against the
#    published closed-form references (Wald 1945; Howard et al.) --------------

def test_gaussian_sprt_llr_increment_matches_textbook_formula():
    # for H0: mu=0, H1: mu=1, sigma=1 the per-observation log-likelihood ratio
    # reduces to (x - 0.5)
    sprt = GaussianSPRT(mu0=0.0, mu1=1.0, sigma=1.0)
    sprt.update(2.0)
    assert sprt.llr == pytest.approx(2.0 - 0.5)
    sprt.update(0.0)
    assert sprt.llr == pytest.approx((2.0 - 0.5) + (0.0 - 0.5))


def test_msprt_mixture_lr_matches_closed_form_reference():
    # Howard et al. closed form for the normal mixture likelihood ratio:
    #   Lambda_n = sqrt(s2 / (s2 + n*t2))
    #            * exp(n^2 * t2 * xbar^2 / (2 * s2 * (s2 + n*t2)))
    msprt = MixtureSPRT(mu0=0.0, sigma=1.0, tau2=1.0)
    msprt.update_many([1.0, 1.0])  # n = 2, xbar = 1.0
    n, s2, t2, xbar = 2, 1.0, 1.0, 1.0
    expected = math.sqrt(s2 / (s2 + n * t2)) * math.exp(
        n**2 * t2 * xbar**2 / (2 * s2 * (s2 + n * t2))
    )
    assert msprt.mixture_lr == pytest.approx(expected)
