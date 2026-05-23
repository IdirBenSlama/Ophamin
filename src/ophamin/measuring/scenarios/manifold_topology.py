"""The Manifold-Topology scenario.

Measures the topology of Kimera's semantic manifold after exposure — the
Betti numbers β₀ (connected components), β₁ (loops), β₂ (voids) that
Kimera's ``TopologicalComplexityAnalyzer`` computes over the geoid point
cloud. A healthy manifold is a *single connected component* (β₀ == 1);
fragmentation (β₀ > 1) means the substrate's meaning-space has split into
disconnected islands.

Pre-registered claim — "manifold connectivity":

  median(β₀ over GWF-cleared cycles that expose topology) == 1

A REFUTED verdict (the manifold fragments, β₀ > 1) surfaces a real
structural defect: meaning-space is not staying connected under exposure.
A VALIDATED verdict pins the manifold as connected — the precondition for
the geodesic-retrieval and walker-traversal the rest of the substrate
assumes.

Secondary evidence (descriptive, not pre-registered): the β₁ / β₂
distributions (loop + void structure), the connected-component rate, and —
when the substrate exposes a geoid/scar graph — the node/edge counts that
back the Console's manifold-topology view.

This scenario is authored against the documented topology contract
(``TopologicalComplexityAnalyzer`` → β₀/β₁/β₂; see the Kimera substrate's
topology blueprint). It extracts Betti numbers from the cycle result under
a documented set of keys and returns INCONCLUSIVE (never a wrong verdict)
when the substrate doesn't expose topology — so it is safe to register and
ship before a live-Kimera run has validated the exact key names.
"""

from __future__ import annotations

from statistics import median
from typing import Any, Iterator, Sequence

from ophamin.seeing.corpus import Corpus, CorpusRecord
from ophamin.measuring.proof import Claim, PillarEvidence, Threshold
from ophamin.measuring.scenarios.base import Scenario, ScenarioScore, Tier
from ophamin.seeing.substrate.base import CycleResult


class ManifoldTopologyScenario(Scenario):
    """β₀ / β₁ / β₂ of Kimera's semantic manifold under exposure."""

    name = "manifold-topology"
    tier = Tier.SCIENTIFIC
    family = "topology"
    runner_path = "examples/run_manifold_topology.py"
    goal = (
        "Measure the topology (β₀/β₁/β₂) of Kimera's semantic manifold "
        "after exposure, and test that it stays connected (β₀ == 1)."
    )
    explanation = (
        "Kimera's manifold should remain a single connected component "
        "(β₀ == 1) under exposure — the precondition for geodesic "
        "retrieval and walker traversal. Fragmentation (β₀ > 1) means "
        "meaning-space has split into disconnected islands. This scenario "
        "reads the Betti numbers Kimera's TopologicalComplexityAnalyzer "
        "computes over the geoid point cloud and pre-registers the "
        "connectivity threshold; β₁ (loops) and β₂ (voids) are reported "
        "as descriptive structure."
    )
    method = "median_betti_0"
    falsification_consequence = (
        "The manifold fragments (median β₀ > 1) — meaning-space splits "
        "into disconnected islands, breaking the geodesic-retrieval and "
        "walker-traversal assumptions the rest of the substrate depends on."
    )
    corpus_name = "linux"
    target = "entity"

    _MIN_BODY_LENGTH = 80
    _MAX_BODY_LENGTH = 4000

    def __init__(self, n_cycles: int = 1000) -> None:
        self.n_cycles = int(n_cycles)

    # -- harness contract --------------------------------------------------

    def analysis_plan(self) -> str:
        return (
            f"Stream up to {self.n_cycles} records through Kimera's entity "
            f"target (Takwin); for each GWF-cleared cycle that exposes "
            f"topology, read β₀/β₁/β₂. Pre-registered threshold: median β₀ "
            f"== 1 (manifold connected). Secondary descriptive evidence "
            f"reports the β₁/β₂ distributions, the connected-component "
            f"rate, and geoid/scar graph node+edge counts when present — "
            f"none post-hoc-claimable."
        )

    def select_records(self, corpus: Corpus) -> Iterator[CorpusRecord]:
        for record in corpus.records():
            body = (record.text or "").strip()
            if len(body) < self._MIN_BODY_LENGTH:
                continue
            if len(body) > self._MAX_BODY_LENGTH:
                body = body[: self._MAX_BODY_LENGTH]
            yield CorpusRecord(
                id=record.id,
                text=body,
                metadata={**record.metadata, "body_length": len(body)},
            )

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                "Kimera's semantic manifold stays a single connected "
                "component under exposure — the median β₀ (zeroth Betti "
                "number, count of connected components) over GWF-cleared "
                "cycles equals 1."
            ),
            operationalization=(
                "median of β₀ across GWF-cleared cycles for which the "
                "substrate exposes a topology measurement"
            ),
            threshold=Threshold("manifold_betti_0_median", "==", 1, "count"),
            h0="median β₀ != 1 (manifold fragmented or degenerate)",
            h1="median β₀ == 1 (manifold connected)",
        )

    # -- result extraction -------------------------------------------------

    @staticmethod
    def _gwf_cleared(result: CycleResult) -> bool:
        if not result.success:
            return False
        raw = result.raw or {}
        if raw.get("gwf_lockdown") is True:
            return False
        verdict = str(raw.get("gwf_verdict", "")).strip().lower()
        if verdict.startswith("blocked") or "lockdown" in verdict:
            return False
        return True

    @staticmethod
    def _betti(result: CycleResult) -> list[int] | None:
        """Extract [β₀, β₁, β₂] from the cycle result, or None if absent.

        Documented-key fallback (the substrate may surface topology under
        a nested ``topology`` block, a ``betti_numbers`` list, or flat
        ``betti_0/1/2`` keys). Returns None — never a guess — when no
        recognized topology key is present.
        """
        if not result.success:
            return None
        raw = result.raw or {}
        candidate: Any = None
        block = raw.get("topology")
        if not isinstance(block, dict):
            block = raw.get("topological_complexity")
        if isinstance(block, dict):
            candidate = (
                block.get("betti_numbers")
                or block.get("betti")
                or [block.get("b0"), block.get("b1"), block.get("b2")]
            )
        if not candidate or candidate[0] is None:
            flat = [raw.get("betti_0"), raw.get("betti_1"), raw.get("betti_2")]
            if any(x is not None for x in flat):
                candidate = flat
        if not candidate or candidate[0] is None:
            return None
        out: list[int] = []
        for i in range(3):
            val = candidate[i] if i < len(candidate) else 0
            try:
                out.append(int(val) if val is not None else 0)
            except (TypeError, ValueError):
                return None
        return out

    @staticmethod
    def _graph_counts(result: CycleResult) -> tuple[int, int] | None:
        """(#geoid nodes, #scar edges) if the substrate exposes a graph."""
        raw = result.raw or {}
        graph = raw.get("geoid_graph") or raw.get("manifold_graph")
        if not isinstance(graph, dict):
            return None
        nodes = graph.get("nodes")
        edges = graph.get("edges")
        if isinstance(nodes, list) and isinstance(edges, list):
            return len(nodes), len(edges)
        n = graph.get("n_nodes")
        e = graph.get("n_edges")
        if isinstance(n, int) and isinstance(e, int):
            return n, e
        return None

    @staticmethod
    def _dist(values: Sequence[float]) -> dict[str, float]:
        if not values:
            return {"n": 0, "min": 0.0, "max": 0.0, "median": 0.0}
        s = sorted(float(v) for v in values)
        return {
            "n": len(s),
            "min": s[0],
            "max": s[-1],
            "median": float(median(s)),
        }

    # -- score -------------------------------------------------------------

    def score(
        self, cycle_results: list[CycleResult], records: list[CorpusRecord]
    ) -> ScenarioScore:
        n = len(cycle_results)
        adapter_errors = 0
        b0_values: list[int] = []
        b1_values: list[int] = []
        b2_values: list[int] = []
        connected = 0
        graph_nodes_max = 0
        graph_edges_max = 0
        for result in cycle_results:
            if (result.halt_mode or "").strip().lower() == "adapter_error":
                adapter_errors += 1
                continue
            if not self._gwf_cleared(result):
                continue
            betti = self._betti(result)
            if betti is None:
                continue
            b0_values.append(betti[0])
            b1_values.append(betti[1])
            b2_values.append(betti[2])
            if betti[0] == 1:
                connected += 1
            counts = self._graph_counts(result)
            if counts:
                graph_nodes_max = max(graph_nodes_max, counts[0])
                graph_edges_max = max(graph_edges_max, counts[1])

        measured = len(b0_values)
        b0_median = float(median(b0_values)) if b0_values else 0.0
        connected_rate = connected / measured if measured else 0.0

        evidence = [
            PillarEvidence(
                pillar="O.topology.manifold_betti_0",
                statistic_name="manifold_betti_0_median",
                statistic_value=b0_median,
                library="ophamin",
                library_version="0.1.0",
                cross_check="n/a",
                detail={
                    "distribution": self._dist(b0_values),
                    "connected_component_rate": connected_rate,
                    "cycles_measured": measured,
                    "n_cycles": n,
                    "adapter_errors": adapter_errors,
                },
            ),
            PillarEvidence(
                pillar="O.topology.manifold_betti_1",
                statistic_name="manifold_betti_1_median",
                statistic_value=self._dist(b1_values)["median"],
                library="ophamin",
                library_version="0.1.0",
                cross_check="n/a",
                detail={"distribution": self._dist(b1_values),
                        "note": "loops (1-cycles) in the geoid manifold"},
            ),
            PillarEvidence(
                pillar="O.topology.manifold_betti_2",
                statistic_name="manifold_betti_2_median",
                statistic_value=self._dist(b2_values)["median"],
                library="ophamin",
                library_version="0.1.0",
                cross_check="n/a",
                detail={"distribution": self._dist(b2_values),
                        "note": "voids (2-cycles) in the geoid manifold"},
            ),
            PillarEvidence(
                pillar="O.topology.geoid_graph",
                statistic_name="geoid_graph_nodes_max",
                statistic_value=float(graph_nodes_max),
                library="ophamin",
                library_version="0.1.0",
                cross_check="n/a",
                detail={
                    "nodes_max": graph_nodes_max,
                    "edges_max": graph_edges_max,
                    "note": (
                        "geoid/scar graph size when the substrate exposes "
                        "it — backs the Console manifold-topology view"
                    ),
                },
            ),
        ]

        inconclusive = measured < 10
        reasoning = (
            f"manifold topology measured on {measured}/{n - adapter_errors} "
            f"GWF-cleared cycles; median β₀ = {b0_median:.0f} "
            f"(connected-component rate {connected_rate:.1%}); "
            f"median β₁ = {self._dist(b1_values)['median']:.0f}, "
            f"median β₂ = {self._dist(b2_values)['median']:.0f}; "
            f"geoid graph up to {graph_nodes_max} nodes / {graph_edges_max} "
            f"edges; {adapter_errors} adapter errors"
        )
        if inconclusive:
            reasoning += (
                "; too few cycles exposed a topology measurement to decide "
                "(substrate may not surface β-numbers in this build)"
            )

        return ScenarioScore(
            observed_value=b0_median,
            evidence=evidence,
            inconclusive=inconclusive,
            reasoning=reasoning,
        )
