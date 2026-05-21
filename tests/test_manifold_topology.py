"""Tests for the Manifold-Topology scenario.

The scenario reads Betti numbers (β₀/β₁/β₂) from the substrate's cycle
results and pre-registers "the manifold stays connected (median β₀ == 1)".
These tests pin the metadata contract, the claim, and the scoring across
the three regimes — connected (validated), fragmented (refuted), and
no-topology-exposed (inconclusive) — using synthetic CycleResults.
"""

from __future__ import annotations

from ophamin.measuring.scenarios import SCENARIOS
from ophamin.measuring.scenarios.manifold_topology import ManifoldTopologyScenario
from ophamin.measuring.scenarios.base import Tier
from ophamin.seeing.substrate.base import CycleResult


def _cleared(raw: dict) -> dict:
    return {"gwf_verdict": "cleared", **raw}


def _cycles(n: int, raw: dict) -> list[CycleResult]:
    return [
        CycleResult(cycle_index=i, success=True, halt_mode="exhausted", raw=_cleared(raw))
        for i in range(n)
    ]


class TestMetadata:
    def test_registered(self) -> None:
        assert "manifold-topology" in SCENARIOS

    def test_metadata_contract(self) -> None:
        s = ManifoldTopologyScenario()
        assert s.name == "manifold-topology"
        assert s.tier == Tier.SCIENTIFIC
        assert s.family == "topology"
        assert s.goal and s.explanation

    def test_claim_threshold(self) -> None:
        c = ManifoldTopologyScenario().build_claim()
        assert c.threshold.metric == "manifold_betti_0_median"
        assert c.threshold.comparator == "=="
        assert c.threshold.value == 1


class TestScoring:
    def test_connected_validates(self) -> None:
        """β₀ == 1 across cycles → median 1 → claim satisfied."""
        s = ManifoldTopologyScenario()
        results = _cycles(12, {"topology": {"betti_numbers": [1, 3, 2]},
                               "geoid_graph": {"n_nodes": 40, "n_edges": 120}})
        score = s.score(results, [])
        assert score.observed_value == 1.0
        assert score.inconclusive is False
        assert s.build_claim().threshold.decide(score.observed_value) is True
        # graph counts surface for the Console manifold view
        graph_ev = next(e for e in score.evidence
                        if e.statistic_name == "geoid_graph_nodes_max")
        assert graph_ev.detail["nodes_max"] == 40
        assert graph_ev.detail["edges_max"] == 120

    def test_fragmented_refutes(self) -> None:
        """β₀ == 2 (two disconnected islands) → claim fails."""
        s = ManifoldTopologyScenario()
        results = _cycles(12, {"betti_0": 2, "betti_1": 5, "betti_2": 1})
        score = s.score(results, [])
        assert score.observed_value == 2.0
        assert score.inconclusive is False
        assert s.build_claim().threshold.decide(score.observed_value) is False

    def test_no_topology_is_inconclusive(self) -> None:
        """A substrate that never exposes β-numbers → inconclusive, not wrong."""
        s = ManifoldTopologyScenario()
        results = _cycles(12, {})  # GWF-cleared but no topology key
        score = s.score(results, [])
        assert score.inconclusive is True

    def test_too_few_measured_is_inconclusive(self) -> None:
        s = ManifoldTopologyScenario()
        results = _cycles(3, {"betti_0": 1, "betti_1": 0, "betti_2": 0})
        score = s.score(results, [])
        assert score.inconclusive is True

    def test_gwf_blocked_cycles_excluded(self) -> None:
        """Blocked cycles don't contribute a topology measurement."""
        s = ManifoldTopologyScenario()
        blocked = [
            CycleResult(cycle_index=i, success=True, halt_mode="exhausted",
                        raw={"gwf_verdict": "blocked", "betti_0": 1})
            for i in range(12)
        ]
        score = s.score(blocked, [])
        assert score.inconclusive is True  # nothing cleared → nothing measured
