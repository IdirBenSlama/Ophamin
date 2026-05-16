"""N-fold robustness and validation (N pillar).

Split generation is delegated to scikit-learn's battle-tested
``sklearn.model_selection`` splitters — ``KFold``, ``ShuffleSplit`` (Monte
Carlo CV), and their group-aware variants ``GroupKFold`` / ``GroupShuffleSplit``
(the subject-wise / record-wise distinction that prevents data leakage).

The framework's own thin glue is only:
  * permuting each split's indices so *presentation order* varies as well as
    membership (the N pillar tests order-independence, not just subset choice);
  * ``cross_validate`` — applying an arbitrary evaluator callable over the
    splits and aggregating, since scikit-learn's own ``cross_validate`` is
    estimator-shaped and this framework evaluates metric streams.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, Iterable

import numpy as np
from sklearn.model_selection import (
    GroupKFold,
    GroupShuffleSplit,
    KFold,
    ShuffleSplit,
)
from sklearn.utils import resample

Evaluator = Callable[[list[Any], list[Any]], float]

_Z95 = 1.959963984540054  # standard normal 97.5th percentile


@dataclass
class CVSplit:
    """One train/test partition. Index lists are already in presentation order."""

    train_indices: list[int]
    test_indices: list[int]


@dataclass
class CVResult:
    """Aggregate of an evaluator applied across many splits."""

    method: str
    scores: list[float]
    mean: float
    std: float
    sem: float
    ci_low: float
    ci_high: float
    n_splits: int

    def summary(self) -> str:
        return (
            f"{self.method}: mean={self.mean:.4g} std={self.std:.4g} "
            f"95%CI=({self.ci_low:.4g}, {self.ci_high:.4g}) over {self.n_splits} splits"
        )


def _seed(rng: Any) -> Any:
    """Normalise an rng argument to a value scikit-learn's ``random_state`` accepts."""
    if rng is None:
        return None
    if isinstance(rng, (int, np.integer)):
        return int(rng)
    if isinstance(rng, np.random.RandomState):
        return rng
    if isinstance(rng, np.random.Generator):
        return int(rng.integers(0, 2**32 - 1))
    raise TypeError(f"unsupported rng type for cross-validation: {type(rng)!r}")


def _resolve_groups(n_items: int, groups: Any) -> list[Any] | None:
    if groups is None:
        return None
    groups_list = list(groups)
    if len(groups_list) != n_items:
        raise ValueError("groups must have one label per item")
    return groups_list


def _to_splits(sklearn_splits: Any, order_rng: np.random.Generator) -> list[CVSplit]:
    """Convert scikit-learn (train, test) index arrays into order-permuted CVSplits."""
    out: list[CVSplit] = []
    for train_idx, test_idx in sklearn_splits:
        train = np.asarray(train_idx, dtype=int)
        test = np.asarray(test_idx, dtype=int)
        order_rng.shuffle(train)
        order_rng.shuffle(test)
        out.append(CVSplit(train.tolist(), test.tolist()))
    return out


def monte_carlo_splits(
    n_items: int,
    n_iterations: int,
    train_fraction: float,
    rng: Any = None,
    groups: Any = None,
) -> list[CVSplit]:
    """Repeated random holdout splits — scikit-learn ``ShuffleSplit`` / ``GroupShuffleSplit``."""
    if n_items < 2:
        raise ValueError("need at least 2 items to split")
    if not (0.0 < train_fraction < 1.0):
        raise ValueError("train_fraction must be in (0, 1)")
    if n_iterations < 1:
        raise ValueError("n_iterations must be >= 1")
    grp = _resolve_groups(n_items, groups)
    seed = _seed(rng)
    order_rng = np.random.default_rng(seed if isinstance(seed, int) else None)
    x = np.zeros((n_items, 1))

    if grp is None:
        splitter = ShuffleSplit(
            n_splits=n_iterations, train_size=train_fraction, random_state=seed
        )
        return _to_splits(splitter.split(x), order_rng)

    if len(set(grp)) < 2:
        raise ValueError("need at least 2 distinct groups for group-aware splitting")
    splitter = GroupShuffleSplit(
        n_splits=n_iterations, train_size=train_fraction, random_state=seed
    )
    return _to_splits(splitter.split(x, groups=grp), order_rng)


def k_fold_splits(
    n_items: int, k: int, rng: Any = None, shuffle: bool = True, groups: Any = None
) -> list[CVSplit]:
    """k mutually exclusive folds — scikit-learn ``KFold`` / ``GroupKFold``."""
    if k < 2:
        raise ValueError("k must be >= 2")
    grp = _resolve_groups(n_items, groups)
    seed = _seed(rng)
    order_rng = np.random.default_rng(seed if isinstance(seed, int) else None)
    x = np.zeros((n_items, 1))

    if grp is None:
        if k > n_items:
            raise ValueError("k cannot exceed the number of items")
        splitter = KFold(
            n_splits=k, shuffle=shuffle, random_state=seed if shuffle else None
        )
        return _to_splits(splitter.split(x), order_rng)

    if k > len(set(grp)):
        raise ValueError("k cannot exceed the number of distinct groups")
    # GroupKFold gained shuffle/random_state in recent scikit-learn.
    try:
        splitter = GroupKFold(
            n_splits=k, shuffle=shuffle, random_state=seed if shuffle else None
        )
    except TypeError:  # older scikit-learn — GroupKFold is deterministic
        splitter = GroupKFold(n_splits=k)
    return _to_splits(splitter.split(x, groups=grp), order_rng)


def bootstrap_splits(n_items: int, n_iterations: int, rng: Any = None) -> list[CVSplit]:
    """Sampling with replacement (``sklearn.utils.resample``); test set is out-of-bag."""
    if n_items < 2:
        raise ValueError("need at least 2 items to bootstrap")
    if n_iterations < 1:
        raise ValueError("n_iterations must be >= 1")
    seed = _seed(rng)
    base = seed if isinstance(seed, int) else 0
    splits: list[CVSplit] = []
    for i in range(n_iterations):
        train_idx = resample(
            np.arange(n_items), replace=True, n_samples=n_items, random_state=base + i
        )
        oob = sorted(set(range(n_items)) - set(train_idx.tolist()))
        if not oob:  # vanishingly rare; skip rather than emit an empty test set
            continue
        splits.append(CVSplit(train_idx.tolist(), oob))
    if not splits:
        raise RuntimeError("every bootstrap draw covered all items — increase n_items")
    return splits


def cross_validate(items: Iterable[Any], evaluator: Evaluator, splits: list[CVSplit]) -> CVResult:
    """Apply ``evaluator`` across ``splits`` and aggregate the scores."""
    items_list: list[Any] = list(items)
    if not splits:
        raise ValueError("no splits provided")
    scores: list[float] = []
    for sp in splits:
        train = [items_list[i] for i in sp.train_indices]
        test = [items_list[i] for i in sp.test_indices]
        scores.append(float(evaluator(train, test)))
    arr = np.asarray(scores, dtype=float)
    mean = float(arr.mean())
    std = float(arr.std(ddof=1)) if arr.size > 1 else 0.0
    sem = std / math.sqrt(arr.size) if arr.size > 0 else 0.0
    return CVResult(
        method="custom",
        scores=scores,
        mean=mean,
        std=std,
        sem=sem,
        ci_low=mean - _Z95 * sem,
        ci_high=mean + _Z95 * sem,
        n_splits=len(splits),
    )


def monte_carlo_cv(
    items: Iterable[Any],
    evaluator: Evaluator,
    n_iterations: int = 200,
    train_fraction: float = 0.7,
    rng: Any = None,
    groups: Any = None,
) -> CVResult:
    """Monte Carlo cross-validation — the N-pillar workhorse (scikit-learn-backed)."""
    items_list = list(items)
    splits = monte_carlo_splits(
        len(items_list), n_iterations, train_fraction, rng=rng, groups=groups
    )
    result = cross_validate(items_list, evaluator, splits)
    result.method = "monte_carlo"
    return result


def k_fold_cv(
    items: Iterable[Any],
    evaluator: Evaluator,
    k: int = 5,
    rng: Any = None,
    shuffle: bool = True,
    groups: Any = None,
) -> CVResult:
    """k-fold cross-validation (scikit-learn-backed)."""
    items_list = list(items)
    splits = k_fold_splits(len(items_list), k, rng=rng, shuffle=shuffle, groups=groups)
    result = cross_validate(items_list, evaluator, splits)
    result.method = f"{k}_fold"
    return result


def bootstrap_cv(
    items: Iterable[Any], evaluator: Evaluator, n_iterations: int = 200, rng: Any = None
) -> CVResult:
    """Bootstrap cross-validation with out-of-bag evaluation (scikit-learn-backed)."""
    items_list = list(items)
    splits = bootstrap_splits(len(items_list), n_iterations, rng=rng)
    result = cross_validate(items_list, evaluator, splits)
    result.method = "bootstrap"
    return result
