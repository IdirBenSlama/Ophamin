"""Tests for the order-bearing retrieval baselines.

These pin the refutation of "retrieval conflates order-different histories":
the mean-pool baseline is order-blind by construction (0 on any reorder), but
standard order-aware representations (shingle bigrams; Jaccard on event sets)
separate the same histories. The point is that order-blindness is a property of
the bag representation, not of retrieval.
"""

from __future__ import annotations

from ophamin.comparing.retrieval_baseline import (
    bag_representation_divergence,
    event_set_jaccard_divergence,
    ordered_representation_divergence,
)

# A multiset of position-tagged events in two orders (as the finance scenario
# renders them: position baked in, so the two orders are different SETS).
_LO = ["day1 +0.05", "day2 -0.03", "day3 +0.02", "day4 -0.08"]
_HI = ["day1 -0.08", "day2 +0.02", "day3 -0.03", "day4 +0.05"]

# Content-only events (no position tag): SAME set, only the ORDER differs.
_VAL_A = ["+0.05", "-0.03", "+0.02", "-0.08"]
_VAL_B = ["-0.08", "+0.02", "-0.03", "+0.05"]


class TestBagIsOrderBlind:
    def test_position_tagged_mean_pool_is_zero(self):
        # the proof's RAG metric: mean-pool conflates (value<->position averaged out)
        assert bag_representation_divergence(_LO, _HI) == 0.0

    def test_content_only_mean_pool_is_zero(self):
        assert bag_representation_divergence(_VAL_A, _VAL_B) == 0.0


class TestOrderedSeparates:
    def test_shingle_separates_position_tagged(self):
        assert ordered_representation_divergence(_LO, _HI) > 0.0

    def test_shingle_separates_content_only_reorder(self):
        # even with an identical SET, the order-bearing shingle is nonzero
        assert ordered_representation_divergence(_VAL_A, _VAL_B) > 0.0

    def test_identical_sequence_is_zero(self):
        assert ordered_representation_divergence(_LO, _LO) == 0.0

    def test_empty_is_zero(self):
        assert ordered_representation_divergence([], _LO) == 0.0


class TestMatchedMetric:
    def test_jaccard_separates_position_tagged(self):
        # SAME metric the scenario uses on Kimera's prime sets -> RAG also separates
        assert event_set_jaccard_divergence(_LO, _HI) > 0.5

    def test_jaccard_zero_for_identical_set_content_only(self):
        # content-only reorder is the SAME set -> Jaccard distance 0 (only order
        # differs); this is why the position-free contrast must use the shingle
        assert event_set_jaccard_divergence(_VAL_A, _VAL_B) == 0.0

    def test_jaccard_identical_is_zero(self):
        assert event_set_jaccard_divergence(_LO, _LO) == 0.0
