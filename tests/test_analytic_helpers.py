"""Tests for measuring/analytic_helpers — pingouin / POT / infomeasure / umap wrappers."""

from __future__ import annotations

import random

import pytest

from ophamin.measuring.analytic_helpers import (
    effect_size_cohens_d_with_ci,
    multiple_comparisons_correction,
    mutual_information_continuous,
    reduce_to_2d,
    wasserstein_distance_1d,
)


# --------------------------------------------------------------------------
# pingouin: Cohen's d with CI
# --------------------------------------------------------------------------


def test_cohens_d_zero_when_samples_equal():
    a = [1, 2, 3, 4, 5, 6, 7, 8]
    b = [1, 2, 3, 4, 5, 6, 7, 8]
    out = effect_size_cohens_d_with_ci(a, b)
    assert abs(out["cohens_d"]) < 1e-9
    assert out["ci_low"] < 0 < out["ci_high"]
    assert out["n_a"] == 8
    assert out["n_b"] == 8


def test_cohens_d_large_when_samples_separated():
    rng = random.Random(0)
    a = [rng.gauss(0, 1) for _ in range(50)]
    b = [rng.gauss(3, 1) for _ in range(50)]
    out = effect_size_cohens_d_with_ci(a, b)
    # Mean diff ~3 with sd=1 → d ≈ 3 (negative because pingouin direction).
    assert abs(out["cohens_d"]) >= 2.0


def test_cohens_d_loud_failure_on_tiny_samples():
    with pytest.raises(ValueError, match="≥ 2 observations"):
        effect_size_cohens_d_with_ci([1.0], [2.0])


def test_cohens_d_returns_ci_in_correct_direction():
    # Use samples with variance — equal-element samples give pooled-SD=0
    # which makes Cohen's d undefined.
    out = effect_size_cohens_d_with_ci(
        [0.0, 0.1, -0.1, 0.05, -0.05],
        [1.0, 1.1, 0.9, 1.05, 0.95],
    )
    # CI must contain the point estimate.
    assert out["ci_low"] <= out["cohens_d"] <= out["ci_high"]


# --------------------------------------------------------------------------
# pingouin: multiple-comparisons correction
# --------------------------------------------------------------------------


def test_fdr_correction_returns_correct_shape():
    p_values = [0.001, 0.01, 0.05, 0.1, 0.5]
    out = multiple_comparisons_correction(p_values, method="fdr_bh", alpha=0.05)
    assert len(out["reject"]) == 5
    assert len(out["p_corrected"]) == 5
    assert all(isinstance(b, bool) for b in out["reject"])
    # Most-significant p MUST be rejected at α=0.05.
    assert out["reject"][0] is True


def test_bonferroni_more_conservative_than_fdr():
    p_values = [0.01, 0.02, 0.03, 0.04]
    bonf = multiple_comparisons_correction(p_values, method="bonferroni", alpha=0.05)
    fdr = multiple_comparisons_correction(p_values, method="fdr_bh", alpha=0.05)
    n_reject_bonf = sum(bonf["reject"])
    n_reject_fdr = sum(fdr["reject"])
    assert n_reject_bonf <= n_reject_fdr


# --------------------------------------------------------------------------
# POT: 1-D Wasserstein
# --------------------------------------------------------------------------


def test_wasserstein_zero_for_identical():
    a = [1.0, 2.0, 3.0]
    b = [1.0, 2.0, 3.0]
    assert wasserstein_distance_1d(a, b) == pytest.approx(0.0, abs=1e-9)


def test_wasserstein_equals_mean_diff_for_uniform_shifts():
    """Two uniform distributions translated by k → W1 = k."""
    a = [0.0, 1.0, 2.0, 3.0, 4.0]
    b = [10.0, 11.0, 12.0, 13.0, 14.0]
    assert wasserstein_distance_1d(a, b) == pytest.approx(10.0, rel=1e-3)


def test_wasserstein_loud_failure_on_empty():
    with pytest.raises(ValueError, match="non-empty"):
        wasserstein_distance_1d([], [1.0])


# --------------------------------------------------------------------------
# infomeasure: continuous MI
# --------------------------------------------------------------------------


def test_mutual_information_low_for_independent():
    rng = random.Random(0)
    x = [rng.gauss(0, 1) for _ in range(500)]
    y = [rng.gauss(0, 1) for _ in range(500)]
    mi = mutual_information_continuous(x, y, k=4)
    # Independent → MI ≈ 0 (small estimator bias allowed).
    assert mi < 0.3


def test_mutual_information_high_for_dependent():
    rng = random.Random(0)
    x = [rng.gauss(0, 1) for _ in range(500)]
    y = [xi * 0.95 + rng.gauss(0, 0.1) for xi in x]
    mi = mutual_information_continuous(x, y, k=4)
    # Strongly correlated → MI well above 0.
    assert mi > 0.8


def test_mutual_information_loud_failure_on_length_mismatch():
    with pytest.raises(ValueError, match="same length"):
        mutual_information_continuous([1.0, 2.0], [1.0, 2.0, 3.0])


def test_mutual_information_loud_failure_on_too_few_samples():
    with pytest.raises(ValueError, match="at least k\\+1"):
        mutual_information_continuous([1.0, 2.0], [1.0, 2.0], k=4)


# --------------------------------------------------------------------------
# umap: 2-D embedding
# --------------------------------------------------------------------------


def test_umap_reduces_to_2d_correct_shape():
    rng = random.Random(0)
    embeddings = [
        [rng.gauss(0, 1) for _ in range(10)]
        for _ in range(20)
    ]
    coords = reduce_to_2d(embeddings, n_neighbors=5, random_state=42)
    assert len(coords) == 20
    for c in coords:
        assert len(c) == 2
        assert isinstance(c[0], float)
        assert isinstance(c[1], float)


def test_umap_loud_failure_on_too_few_samples():
    with pytest.raises(ValueError, match="≥ 2 samples"):
        reduce_to_2d([[1.0, 2.0, 3.0]])


def test_umap_loud_failure_on_wrong_shape():
    with pytest.raises(ValueError, match="2-D"):
        reduce_to_2d([1.0, 2.0, 3.0])    # 1-D, not 2-D


def test_umap_is_deterministic_with_random_state():
    rng = random.Random(0)
    embeddings = [
        [rng.gauss(0, 1) for _ in range(5)]
        for _ in range(10)
    ]
    a = reduce_to_2d(embeddings, n_neighbors=3, random_state=42)
    b = reduce_to_2d(embeddings, n_neighbors=3, random_state=42)
    for ca, cb in zip(a, b):
        assert ca[0] == pytest.approx(cb[0], abs=1e-5)
        assert ca[1] == pytest.approx(cb[1], abs=1e-5)
