"""Order-keeping prime-chain trajectory metrics — they must see the path the
set/Jaccard metric is blind to.

The thesis (Ophamin charter §7, brick #1): Kimera's differentiator is
path-dependence, yet the memory scenarios measure it with order-blind Jaccard
over ``prime_set``. A re-ordering of the SAME primes is *identical* to a set
metric and *divergent* to a trajectory metric. These tests pin that contrast so
it can never silently regress.
"""

import math

from ophamin.seeing.substrate.observables import (
    energy_path_divergence,
    jaccard,
    prime_energy_path,
    sequence_edit_divergence,
)

WALK = ["2", "3", "5", "7", "11", "13"]
REORDER = ["13", "11", "7", "5", "3", "2"]  # same multiset, reversed order
DISJOINT = ["17", "19", "23", "29"]


def _set_divergence(a, b):
    """The metric the memory scenarios use today: 1 - Jaccard(prime_set)."""
    return 1.0 - jaccard(frozenset(a), frozenset(b))


def test_set_metric_is_blind_to_reorder():
    # The exact gap brick #1 closes: a pure reorder is invisible to the set metric.
    assert _set_divergence(WALK, REORDER) == 0.0


def test_edit_divergence_sees_reorder():
    assert sequence_edit_divergence(WALK, REORDER) > 0.0
    assert sequence_edit_divergence(WALK, list(WALK)) == 0.0
    assert 0.0 <= sequence_edit_divergence(WALK, DISJOINT) <= 1.0


def test_edit_divergence_empty_cases():
    assert sequence_edit_divergence([], []) == 0.0
    assert sequence_edit_divergence(WALK, []) == 1.0
    assert sequence_edit_divergence([], WALK) == 1.0


def test_energy_path_divergence_sees_reorder():
    en = energy_path_divergence(WALK, REORDER)
    assert en is not None and en > 0.0
    assert (energy_path_divergence(WALK, list(WALK)) or 0.0) < 1e-9


def test_energy_path_bounds_and_gaps():
    d = energy_path_divergence(WALK, DISJOINT)
    assert d is not None and 0.0 <= d <= 1.0
    # No usable prime energy → None (a gap, never a fabricated 0.0).
    assert energy_path_divergence(["x", "y"], WALK) is None
    assert energy_path_divergence([], WALK) is None


def test_prime_energy_path_is_log_p():
    assert prime_energy_path(["2", "3"]) == (math.log(2), math.log(3))
    # Only integer primes > 1 contribute; address fragments / 0 / 1 / negatives drop.
    assert prime_energy_path(["1", "0", "-5", "foo"]) == ()
