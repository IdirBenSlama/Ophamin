"""Tests for the falsifiable probe-specific permanence metric.

The point is that it CAN return < 1.0 — a recognised-but-not-deepened
re-exposure does not count — unlike the global-scar counter, which is ~1.0 by
construction. These pin that falsifiability.
"""

from __future__ import annotations

from ophamin.comparing.permanence import (
    global_counter_is_degenerate,
    probe_specific_permanence,
)


class TestProbeSpecific:
    def test_always_deepens_is_permanent(self):
        r = probe_specific_permanence([1.0, 2.0, 3.0, 4.0])
        assert r["assessable"] is True
        assert r["proportion_deepened"] == 1.0
        assert r["permanent"] is True

    def test_a_flat_reexposure_breaks_permanence(self):
        # depth did not increase on one re-exposure -> NOT permanent (the thing
        # the global counter can never show)
        r = probe_specific_permanence([1.0, 1.0, 2.0])
        assert r["permanent"] is False
        assert r["proportion_deepened"] == 0.5
        assert r["n_zero_or_negative"] == 1

    def test_decreasing_is_zero(self):
        r = probe_specific_permanence([3.0, 2.0, 1.0])
        assert r["proportion_deepened"] == 0.0
        assert r["permanent"] is False

    def test_non_strict_counts_equal(self):
        r = probe_specific_permanence([1.0, 1.0, 2.0], strict=False)
        assert r["proportion_deepened"] == 1.0

    def test_too_few_observations_not_assessable(self):
        r = probe_specific_permanence([5.0])
        assert r["assessable"] is False
        assert r["n_transitions"] == 0


class TestGlobalCounterDegeneracy:
    def test_monotone_constant_delta_flagged(self):
        # the shape of the genesis proof's scar_series: [1,2,3,...] (delta=const)
        r = global_counter_is_degenerate([1, 2, 3, 4, 5, 6])
        assert r["monotone_nondecreasing"] is True
        assert r["constant_delta"] is True
        assert r["trivially_permanent"] is True

    def test_constant_gap_delta(self):
        # a constant delta of 8 (the interleave gap) -> cadence, not content
        r = global_counter_is_degenerate([8, 16, 24, 32])
        assert r["constant_delta"] is True
        assert r["delta_value"] == 8.0

    def test_non_monotone_not_trivially_permanent(self):
        r = global_counter_is_degenerate([1, 2, 1, 3])
        assert r["monotone_nondecreasing"] is False
        assert r["trivially_permanent"] is False
