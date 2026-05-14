"""Tests for the N pillar — cross-validation.

The key assertions cross-check Ophamin's splits against scikit-learn's own
splitters directly: the framework must reproduce ``ShuffleSplit`` / ``KFold``
membership exactly (it only permutes index *order* on top).
"""

import numpy as np
import pytest
from sklearn.model_selection import KFold, ShuffleSplit

from ophamin.robustness.cross_validation import (
    bootstrap_splits,
    cross_validate,
    k_fold_splits,
    monte_carlo_cv,
    monte_carlo_splits,
)


def test_monte_carlo_splits_membership_matches_sklearn_shufflesplit():
    n, iters, frac, seed = 20, 30, 0.7, 0
    ours = monte_carlo_splits(n, iters, frac, rng=seed)
    ref = list(
        ShuffleSplit(n_splits=iters, train_size=frac, random_state=seed).split(
            np.zeros((n, 1))
        )
    )
    assert len(ours) == len(ref)
    for sp, (train, test) in zip(ours, ref):
        assert set(sp.train_indices) == set(train.tolist())
        assert set(sp.test_indices) == set(test.tolist())


def test_k_fold_splits_membership_matches_sklearn_kfold():
    n, k, seed = 20, 5, 0
    ours = k_fold_splits(n, k, rng=seed, shuffle=True)
    ref = list(KFold(n_splits=k, shuffle=True, random_state=seed).split(np.zeros((n, 1))))
    for sp, (_train, test) in zip(ours, ref):
        assert set(sp.test_indices) == set(test.tolist())
    all_test = sorted(i for sp in ours for i in sp.test_indices)
    assert all_test == list(range(n))


def test_monte_carlo_splits_are_disjoint_and_sized():
    splits = monte_carlo_splits(n_items=20, n_iterations=50, train_fraction=0.7, rng=0)
    assert len(splits) == 50
    for sp in splits:
        assert set(sp.train_indices).isdisjoint(sp.test_indices)
        assert len(sp.train_indices) + len(sp.test_indices) == 20


def test_monte_carlo_splits_group_aware_keeps_groups_together():
    groups = [0, 0, 1, 1, 2, 2, 3, 3, 4, 4]
    splits = monte_carlo_splits(10, 30, 0.6, rng=1, groups=groups)
    for sp in splits:
        train_groups = {groups[i] for i in sp.train_indices}
        test_groups = {groups[i] for i in sp.test_indices}
        assert train_groups.isdisjoint(test_groups)


def test_k_fold_group_aware_keeps_groups_together():
    groups = [g for g in range(6) for _ in range(3)]  # 6 groups of 3
    for sp in k_fold_splits(18, 3, rng=0, groups=groups):
        train_groups = {groups[i] for i in sp.train_indices}
        test_groups = {groups[i] for i in sp.test_indices}
        assert train_groups.isdisjoint(test_groups)


def test_bootstrap_test_set_is_out_of_bag():
    for sp in bootstrap_splits(n_items=30, n_iterations=20, rng=0):
        assert len(sp.train_indices) == 30  # sampled with replacement
        assert set(sp.test_indices).isdisjoint(sp.train_indices)


def test_monte_carlo_cv_on_constant_series_has_zero_spread():
    result = monte_carlo_cv(
        [5.0] * 30, evaluator=lambda _tr, te: float(np.mean(te)), n_iterations=100, rng=0
    )
    assert result.mean == pytest.approx(5.0)
    assert result.std == pytest.approx(0.0)
    assert result.method == "monte_carlo"


def test_cross_validate_aggregates_scores():
    splits = monte_carlo_splits(10, n_iterations=20, train_fraction=0.5, rng=0)
    result = cross_validate(list(range(10)), lambda tr, te: float(len(te)), splits)
    assert result.mean == pytest.approx(5.0)
    assert result.n_splits == 20


def test_invalid_train_fraction_raises():
    with pytest.raises(ValueError):
        monte_carlo_splits(10, n_iterations=5, train_fraction=1.5)


def test_k_fold_rejects_k_larger_than_items():
    with pytest.raises(ValueError):
        k_fold_splits(n_items=3, k=5)
