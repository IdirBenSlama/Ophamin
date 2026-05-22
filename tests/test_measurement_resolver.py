"""Tests for the measurement resolver — routing a missing-measurement need.

Pins: candidate assembly across the three lists, the conservative routing
(don't claim an existing scenario unless name/metric actually overlap), the
always-on grounding requirement (the guardrail), and the spurious-match guard
(generic words must not route to an unrelated existing scenario).
"""

from __future__ import annotations

import pytest

from ophamin.authoring.measurement_resolver import (
    COMPOSE_PRIMITIVES,
    COMPOSE_TEMPLATE,
    SYNTHESIZE,
    resolve_measurement,
)


class TestAssembly:
    def test_returns_ranked_candidates_from_all_three_lists(self):
        r = resolve_measurement("recognition jaccard floor across re-exposures")
        assert r["compose_templates"]      # capability menu
        assert r["compose_pillars"]        # O·F·A·M·I·N pillars
        assert r["wire_toolkits"]          # external toolkit registry
        # ranked descending by score
        scores = [c["score"] for c in r["compose_templates"]]
        assert scores == sorted(scores, reverse=True)

    def test_grounding_always_required(self):
        r = resolve_measurement("anything at all about the substrate dynamics")
        assert r["grounding_required"] is True
        assert r["recognised_standards"]   # the standards an author may cite
        assert "grounding gate" in r["grounding_note"]


class TestRouting:
    def test_existing_scenario_identified_on_real_match(self):
        # name/metric genuinely overlap -> claim the existing scenario.
        r = resolve_measurement(
            "recognition jaccard floor of concept sets across re-exposures")
        assert r["path"] == COMPOSE_TEMPLATE
        assert r["compose_templates"][0]["name"] == "recognition"

    def test_spurious_generic_words_do_not_claim_a_scenario(self):
        # "sustained load" appears in the phi template's description, but a GPU
        # question must NOT be routed to "phi already measures this".
        r = resolve_measurement("GPU thermal throughput under sustained load")
        assert r["path"] != COMPOSE_TEMPLATE
        assert r["path"] in (COMPOSE_PRIMITIVES, SYNTHESIZE)

    def test_novel_need_routes_to_synthesize(self):
        # the partial-cue recall metric is genuinely new — no existing
        # template/pillar covers it -> synthesize a grounded primitive.
        r = resolve_measurement(
            "partial-cue recall: recall an item from a corrupted partial cue, "
            "isolating path-dependent memory from deterministic re-derivation")
        assert r["path"] == SYNTHESIZE
        # but it still surfaces the closest template to build on
        assert r["compose_templates"][0]["name"] in {"recognition", "phi", "manifold-topology"}

    def test_empty_need_raises(self):
        with pytest.raises(ValueError):
            resolve_measurement("   ")


class TestImpl:
    def test_impl_shape(self):
        from ophamin.interfaces._impls import resolve_measurement_impl

        r = resolve_measurement_impl("recall under partial cue")
        assert "path" in r
        assert "compose_templates" in r
        assert r["grounding_required"] is True
