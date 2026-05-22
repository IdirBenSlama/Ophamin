"""The Memory-Order-Hysteresis scenario — Kimera vs standard retrieval, the
honest "is it different from RAG?" proof.

The memory-permanence proof showed Kimera's memory is permanent and
path-dependent in the scar/manifold substrate. The investor's next question is
fair: *how is that different from retrieval-augmented memory (RAG), which the
industry already has?* This proof answers it on the one axis where the two
architectures structurally diverge — **order of experience**.

The structural fact (see ``ophamin.comparing.retrieval_baseline``): a set-based
retriever (TF-IDF, dense embeddings, BM25, FAISS) is a pure function of the
document **set** and the query. Ingesting the same documents in a different
order yields the identical index, identical vectors, identical cosine scores —
identical ranking. Its memory is an **order-blind inventory** (order divergence
= 0, by construction).

Kimera *claims* hysteresis ("order matters" — CLAUDE.md data model). A live
probe (2026-05-22) confirmed it where it lives: presenting the same documents in
a different order, then asking the same query, left **recognition identical**
(concept Jaccard 1.0, Φ identical) but gave the query a **different prime-address**
(``prime_chain`` differs) and left the manifold in a different state (coupling
3.21 vs 2.42). Crucially, an identical-order run twice was **byte-identical**
(determinism), so the order effect is not run-to-run noise.

The decisive, falsifiable design (with a built-in determinism control)
=====================================================================

For each held-out probe, run the same documents through Kimera in:

  * order A  → prime-address  R_A1
  * order A again → R_A2     (the determinism control / noise floor)
  * order B (shuffled) → R_B

  kimera_order_divergence_i = 1 − Jaccard(primes(R_A1), primes(R_B))
  kimera_noise_floor_i      = 1 − Jaccard(primes(R_A1), primes(R_A2))

  order_hysteresis = mean(order_divergence) − mean(noise_floor)

A standard retriever's order divergence is 0.0 (demonstrated, not assumed).

Pre-registered: ``order_hysteresis > 0`` — Kimera's response to an identical,
identically-recognised query depends on the **order** of prior experience
beyond its own (near-zero) run-noise, where a set-based retriever's does not.
Decided only when a paired test (order_divergence > noise_floor) is significant;
else INCONCLUSIVE. If order_hysteresis ≤ 0 the honest finding is that Kimera's
accumulation is **commutative** (the differentiator is permanence, not
hysteresis) — a Kimera construction brief, not an artefact.
"""

from __future__ import annotations

import random
from statistics import mean, median
from typing import Any

from ophamin import __version__
from ophamin.comparing.provenance import ProvenanceGraph
from ophamin.comparing.provenance.lineage import (
    _ophamin_project_root,
    capture_git_commit,
)
from ophamin.comparing.retrieval_baseline import TfidfRetriever, order_divergence
from ophamin.measuring.proof import (
    Claim,
    DatasetRef,
    EmpiricalProofRecord,
    PillarEvidence,
    PreRegistration,
    Reproduction,
    Threshold,
    Verdict,
    content_hash,
)
from ophamin.measuring.scenarios.base import (
    DEFAULT_SIGN_KEY,
    Scenario,
    ScenarioScore,
    Tier,
)
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest

# Curated genesis documents (the "corpus") and disjoint held-out probes (the
# "queries"). Documents are re-ordered; probes are asked identically in both
# orders so the ONLY difference is document order.
_DEFAULT_DOCUMENTS: tuple[str, ...] = (
    "Memory is the deformation of the spherical manifold by experience.",
    "A scar is a permanent topological deformation; it cannot be reset.",
    "The geoid accumulates semantic mass the way Earth accumulates gravity.",
    "Primes are the atoms of the substrate; meaning is indexed by a prime.",
    "Retrieval follows the geodesics of the reshaped manifold, not a key.",
    "The vault stores scars; recall is conditional on the manifold's shape.",
)
_DEFAULT_PROBES: tuple[str, ...] = (
    "The walker traverses the manifold and resolves contradiction by moving.",
    "Resonance binds concepts whose primes share multiplicative structure.",
    "Experience carves the surface and later recall follows that curvature.",
    "Contradiction is the engine; the substrate moves to resolve it.",
    "Meaning is a point on the sphere that experience pushes and deforms.",
    "The prime energy scale is the logarithm of the prime itself.",
)


class MemoryOrderHysteresisScenario(Scenario):
    """Kimera's order-sensitive (hysteretic) memory vs order-invariant retrieval.

    Construct with documents + disjoint probes; call ``run(adapter)`` with a live
    :class:`KimeraAdapter` in **batch** mode. Runs three batches (order A, order
    A again, order B) so the determinism control is real. ``run()`` is fully
    overridden; ``score()`` is unreachable.
    """

    name = "memory-order-hysteresis"
    tier = Tier.SCIENTIFIC
    family = "memory"
    scope = "comparison"
    runner_path = "examples/run_memory_order_hysteresis.py"
    target = "entity"
    goal = (
        "Settle the 'how is this different from RAG?' question on the one axis "
        "where the architectures structurally diverge: does the SAME query, "
        "after the SAME documents in a DIFFERENT order, get a different response "
        "from Kimera (hysteresis) while a set-based retriever returns the "
        "identical ranking (order-blind)?"
    )
    explanation = (
        "A standard retriever is a pure function of the document SET and the "
        "query — ingestion order cannot change its ranking (order divergence = "
        "0, by construction; demonstrated, not assumed). Kimera's data model "
        "claims hysteresis. This proof measures, per held-out probe: "
        "order_divergence = 1 − Jaccard(prime-address | order A, prime-address "
        "| order B), against a determinism control noise_floor = the same with "
        "order A run twice. order_hysteresis = mean(order_divergence) − "
        "mean(noise_floor). Kimera is deterministic for identical input "
        "(noise_floor ≈ 0, verified), so a positive hysteresis is the order "
        "effect, not noise. order_hysteresis > 0 ⇒ Kimera carries the ORDER of "
        "experience where RAG carries only the inventory; ≤ 0 ⇒ accumulation is "
        "commutative (permanence, not hysteresis, is the differentiator)."
    )
    method = "prime_address_order_divergence_vs_determinism_control_and_rag_baseline"
    falsification_consequence = (
        "Kimera's response to an identical, identically-recognised query does "
        "NOT depend on the order of prior experience beyond run-noise — its "
        "accumulation is commutative, like a set-based retriever. The "
        "differentiator would then be permanence + path-depth (memory-permanence "
        "proof), not order-hysteresis. A Kimera construction brief, not an "
        "artefact."
    )

    def __init__(
        self,
        *,
        documents: tuple[str, ...] = _DEFAULT_DOCUMENTS,
        probes: tuple[str, ...] = _DEFAULT_PROBES,
        shuffle_seed: int = 1,
        min_probes: int = 4,
        corpus_label: str = "kimera-genesis",
    ) -> None:
        if len(documents) < 2:
            raise ValueError("need >= 2 documents to define an order")
        if not probes:
            raise ValueError("probes must be non-empty")
        overlap = set(documents) & set(probes)
        if overlap:
            raise ValueError(
                f"documents and probes must be disjoint; {len(overlap)} shared")
        self.documents = tuple(documents)
        self.probes = tuple(probes)
        self.shuffle_seed = int(shuffle_seed)
        self.min_probes = int(min_probes)
        self.corpus_label = str(corpus_label)
        # three batches of (docs + probes)
        self.n_cycles = 3 * (len(self.documents) + len(self.probes))

    # --------------------------------------------------------- ordering ------

    def _order_b(self) -> list[str]:
        """A genuinely different document order (same set)."""
        docs = list(self.documents)
        shuffled = docs[:]
        random.Random(self.shuffle_seed).shuffle(shuffled)
        if shuffled == docs:
            shuffled = list(reversed(docs))
        return shuffled

    # --------------------------------------------------------- extraction ----

    @staticmethod
    def _prime_set(result: CycleResult) -> frozenset[str] | None:
        """The probe's prime-address for the cycle (its ``prime_chain``).

        Falls back to the rosetta/alexandria prime maps if the chain is absent.
        Returns None on failure / no prime address (a gap, not a 0-divergence).
        """
        if not result.success:
            return None
        raw = result.raw or {}
        chain = raw.get("prime_chain")
        if isinstance(chain, list) and chain:
            primes = {str(p).strip() for p in chain if str(p).strip()}
            if primes:
                return frozenset(primes)
        for k in ("rosetta_primes", "alexandria_fused_primes"):
            v = raw.get(k)
            if isinstance(v, dict) and v:
                return frozenset(str(x) for x in v.keys())
        return None

    @staticmethod
    def _state(result: CycleResult) -> dict[str, float | None]:
        raw = result.raw or {} if result.success else {}

        def f(key: str) -> float | None:
            v = raw.get(key)
            return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None

        return {
            "coupling": f("arachne_web_coupling_frobenius"),
            "mass": f("knowledge_mass"),
            "order_param": f("arachne_web_order_parameter"),
        }

    @staticmethod
    def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
        u = a | b
        return len(a & b) / len(u) if u else 1.0

    # --------------------------------------------------------------- claim ---

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                "After the same documents in a different ORDER, the same "
                "identically-recognised query gets a different prime-address "
                "from Kimera (hysteresis) beyond its own run-noise, whereas a "
                "set-based retriever returns the identical ranking (order-blind "
                "by construction): order_hysteresis = mean(order_divergence) − "
                "mean(noise_floor) > 0."
            ),
            operationalization=(
                f"Run {len(self.documents)} documents + {len(self.probes)} "
                "held-out probes through Kimera's entity target (batch) in "
                "order A, order A again (determinism control), and order B "
                "(shuffled). Per probe: order_divergence = 1 − "
                "Jaccard(prime_chain|A, prime_chain|B); noise_floor = 1 − "
                "Jaccard(prime_chain|A1, prime_chain|A2). order_hysteresis = "
                "mean(order_divergence) − mean(noise_floor). Baseline: TF-IDF "
                "retrieval order-divergence over the same docs/queries (= 0). "
                "VALIDATED iff order_hysteresis > 0 with a significant paired "
                "order_divergence > noise_floor test."
            ),
            threshold=Threshold(
                metric="order_hysteresis", comparator=">", value=0.0,
                units="jaccard_distance",
            ),
            h0=(
                "H0: order_hysteresis <= 0 — Kimera's response does not depend "
                "on document order beyond run-noise; accumulation is "
                "commutative, like a set-based retriever"
            ),
            h1=(
                "H1: order_hysteresis > 0 — the same query after the same "
                "documents in a different order gets a different prime-address; "
                "Kimera carries the ORDER of experience (hysteresis) where RAG "
                "carries only the inventory"
            ),
        )

    def analysis_plan(self) -> str:
        return (
            f"Three batches of {len(self.documents)} docs + {len(self.probes)} "
            "probes (order A, A again, B-shuffled) through Kimera entity/batch. "
            "Per probe compute prime-address (prime_chain) order_divergence "
            "(A vs B) and noise_floor (A vs A). order_hysteresis = mean "
            "difference. Baseline TF-IDF order-divergence (= 0) is the contrast. "
            f"INCONCLUSIVE if fewer than {self.min_probes} probes yield a prime "
            "address in all three runs, or the paired Wilcoxon "
            "(order_divergence > noise_floor) is not significant; else "
            "VALIDATED iff order_hysteresis > 0. Per-probe series + aggregate "
            "manifold-state divergence (coupling/mass) are evidence."
        )

    def score(self, cycle_results: list[CycleResult], records: list[Any]) -> ScenarioScore:
        raise NotImplementedError(
            "MemoryOrderHysteresisScenario uses a custom run() loop; "
            "score() is unreachable.")

    # ------------------------------------------------------------------ run --

    def run(
        self,
        substrate: SubstrateUnderTest | None = None,
        *,
        sign_key: bytes = DEFAULT_SIGN_KEY,
    ) -> EmpiricalProofRecord:
        if substrate is None:
            raise ValueError(
                "MemoryOrderHysteresisScenario.run needs a live substrate "
                "adapter in batch mode (each order is one accumulation "
                "trajectory).")

        docs_a = list(self.documents)
        docs_b = self._order_b()
        probes = list(self.probes)
        n_doc = len(docs_a)

        res_a1 = substrate.run_batch(docs_a + probes)
        res_a2 = substrate.run_batch(docs_a + probes)  # determinism control
        res_b = substrate.run_batch(docs_b + probes)

        pa1, pa2, pb = res_a1[n_doc:], res_a2[n_doc:], res_b[n_doc:]

        per_probe: list[dict[str, Any]] = []
        order_divs: list[float] = []
        noise_floors: list[float] = []
        for i, probe in enumerate(probes):
            sA1 = self._prime_set(pa1[i]) if i < len(pa1) else None
            sA2 = self._prime_set(pa2[i]) if i < len(pa2) else None
            sB = self._prime_set(pb[i]) if i < len(pb) else None
            if sA1 is None or sA2 is None or sB is None:
                per_probe.append({"probe": probe[:60], "gap": True})
                continue
            od = 1.0 - self._jaccard(sA1, sB)
            nf = 1.0 - self._jaccard(sA1, sA2)
            order_divs.append(od)
            noise_floors.append(nf)
            per_probe.append({
                "probe": probe[:60],
                "order_divergence": round(od, 6),
                "noise_floor": round(nf, 6),
                "hysteresis": round(od - nf, 6),
                "n_primes_a1": len(sA1), "n_primes_a2": len(sA2), "n_primes_b": len(sB),
                "gap": False,
            })

        n_valid = len(order_divs)
        od_mean = mean(order_divs) if order_divs else 0.0
        nf_mean = mean(noise_floors) if noise_floors else 0.0
        order_hysteresis = od_mean - nf_mean

        # --- RAG baseline: order-divergence of TF-IDF retrieval (structural 0)
        baseline_divs: list[float] = []
        baseline_detail: list[dict[str, Any]] = []
        for probe in probes:
            bd = order_divergence(
                lambda d: TfidfRetriever(d), self.documents, probe,
                seed=self.shuffle_seed)
            baseline_divs.append(bd["order_divergence"])
            baseline_detail.append({
                "probe": probe[:60], "order_divergence": bd["order_divergence"],
                "identical_ranking": bd["identical"], "top1_changed": bd["top1_changed"],
            })
        baseline_mean = mean(baseline_divs) if baseline_divs else 0.0

        # --- aggregate manifold-state order effect (corroboration) ----------
        def _state_div(a: CycleResult, b: CycleResult) -> dict[str, float | None]:
            sa, sb = self._state(a), self._state(b)
            out: dict[str, float | None] = {}
            for k in sa:
                va, vb = sa[k], sb[k]
                out[k] = round(abs(va - vb), 6) if (va is not None and vb is not None) else None
            return out

        # use the last probe cycle (fullest accumulation) for the state read
        state_order = _state_div(pa1[-1], pb[-1]) if pa1 and pb else {}
        state_noise = _state_div(pa1[-1], pa2[-1]) if pa1 and pa2 else {}

        control = self._paired_significance(order_divs, noise_floors)
        significant = control.get("significant", False)
        # A commutative result (order_hysteresis <= 0) is a clean REFUTED, not
        # inconclusive — it answers H0 directly. Only too-little-data, or a
        # POSITIVE effect that fails the significance test, is inconclusive.
        inconclusive = (
            n_valid < self.min_probes
            or (order_hysteresis > 0 and not significant)
        )

        config = {
            "scenario": self.name, "scope": self.scope,
            "n_documents": len(self.documents), "n_probes": len(self.probes),
            "shuffle_seed": self.shuffle_seed,
        }
        dataset = DatasetRef(
            name="kimera-order-hysteresis-trajectory",
            content_hash=content_hash({"docs": docs_a, "probes": probes, "order_b": docs_b}),
            n_records=self.n_cycles,
            source=getattr(substrate, "name", "kimera-swm"),
            kind="substrate-trajectory+order-permutation+rag-baseline",
        )
        prereg = PreRegistration(
            config_hash=content_hash(config), data_hash=dataset.content_hash,
            analysis_plan=self.analysis_plan(),
        )
        claim = self.build_claim()

        reasoning = (
            f"order_hysteresis {order_hysteresis:+.4f} = Kimera order-divergence "
            f"{od_mean:.4f} − noise-floor {nf_mean:.4f} over {n_valid} probes "
            f"(prime-address); RAG (TF-IDF) order-divergence {baseline_mean:.4f} "
            f"(set-based, order-blind by construction)"
        )
        if control.get("p_value") is not None:
            reasoning += (
                f"; paired order>noise Wilcoxon p={control['p_value']:.2g}"
                f"{' (significant — order matters)' if control.get('significant') else ' (NOT significant)'}"
            )
        if state_order:
            reasoning += (
                f"; manifold-state order-effect coupling Δ={state_order.get('coupling')}, "
                f"mass Δ={state_order.get('mass')} (noise coupling Δ={state_noise.get('coupling')})"
            )
        if inconclusive:
            reasoning += (
                "; INCONCLUSIVE — "
                + ("too few probes with a prime address in all three runs"
                   if n_valid < self.min_probes
                   else "order>noise not statistically significant")
            )

        verdict = Verdict.decide(
            observed=order_hysteresis, threshold=claim.threshold,
            inconclusive=inconclusive, reasoning=reasoning,
        )

        evidence = [
            PillarEvidence(
                pillar="O.comparison.order_hysteresis",
                statistic_name="order_hysteresis",
                statistic_value=order_hysteresis,
                library="ophamin",
                library_version=__version__,
                cross_check=control.get("status", "skipped"),
                p_value=control.get("p_value"),
                detail={
                    "scope": "comparison",
                    "kimera_order_divergence_mean": od_mean,
                    "kimera_order_divergence_median": median(order_divs) if order_divs else 0.0,
                    "kimera_noise_floor_mean": nf_mean,
                    "rag_baseline_order_divergence_mean": baseline_mean,
                    "rag_baseline": baseline_detail,
                    "order_hysteresis": order_hysteresis,
                    "n_valid_probes": n_valid,
                    "manifold_state_order_effect": state_order,
                    "manifold_state_noise_floor": state_noise,
                    "per_probe": per_probe,
                    "control": control,
                    "determinism_note": (
                        "noise_floor is the prime-address divergence of order A "
                        "run twice; ~0 confirms Kimera is deterministic for "
                        "identical input, so order_hysteresis is the ORDER "
                        "effect, not run-noise."
                    ),
                    "interpretation": (
                        "order_hysteresis>0 + significant = Kimera carries the "
                        "ORDER of experience (hysteresis) where set-based "
                        "retrieval (RAG, baseline=0) carries only the inventory. "
                        "<=0 = accumulation is commutative; the differentiator "
                        "is permanence + path-depth, not order."
                    ),
                    "grounding_anchor": (
                        "set-based retrieval is order-invariant by construction "
                        "(ophamin.comparing.retrieval_baseline, demonstrated "
                        "divergence 0.0); Kimera hysteresis per CLAUDE.md data "
                        "model + live prime_chain probe (2026-05-22)."
                    ),
                },
            ),
        ]

        prov = ProvenanceGraph()
        a_o = prov.agent("ophamin", role="experimentation_framework", version=__version__)
        a_k = prov.agent("kimera-swm", role="substrate_under_comparison")
        a_r = prov.agent("tfidf-retriever", role="order_invariant_baseline")
        de = prov.entity(f"corpus:{dataset.name}", content_hash=dataset.content_hash,
                         n_records=dataset.n_records, kind=dataset.kind)
        act = prov.activity(f"scenario:{self.name}", target=self.target, n_cycles=self.n_cycles)
        re_ = prov.entity(f"proof:{self.name}")
        prov.used(act, de)
        prov.was_associated_with(act, a_o)
        prov.was_associated_with(act, a_k)
        prov.was_associated_with(act, a_r)
        prov.was_generated_by(re_, act)
        prov.was_attributed_to(re_, a_k)
        prov.was_derived_from(re_, de)

        substrate_commit = ""
        getter = getattr(substrate, "git_commit", None)
        if callable(getter):
            try:
                substrate_commit = str(getter() or "")[:12]
            except Exception:  # noqa: BLE001 — provenance best-effort
                substrate_commit = ""

        proof = EmpiricalProofRecord(
            claim=claim, preregistration=prereg, datasets=[dataset],
            substrate_name=getattr(substrate, "name", "kimera-swm"),
            substrate_git_commit=substrate_commit,
            evidence=evidence, verdict=verdict,
            reproduction=Reproduction(command=self._build_reproduction_command()),
            provenance=prov.to_prov_json(),
            ophamin_version=__version__,
            ophamin_git_commit=capture_git_commit(_ophamin_project_root()),
        )
        proof.sign(sign_key)
        return proof

    @staticmethod
    def _paired_significance(
        order_divs: list[float], noise_floors: list[float]
    ) -> dict[str, Any]:
        """Wilcoxon signed-rank: is per-probe order_divergence > noise_floor?"""
        out: dict[str, Any] = {
            "control": "paired_order_divergence_gt_noise_floor_wilcoxon",
            "n_pairs": len(order_divs),
            "order_divergence_median": round(median(order_divs), 6) if order_divs else 0.0,
            "noise_floor_median": round(median(noise_floors), 6) if noise_floors else 0.0,
        }
        diffs = [o - n for o, n in zip(order_divs, noise_floors)]
        if len(diffs) < 4 or all(d == 0 for d in diffs):
            out.update({"status": "skipped",
                        "reason": "too few pairs or no order effect",
                        "p_value": None, "significant": False})
            return out
        try:
            from scipy.stats import wilcoxon
            # one-sided: order_divergence greater than noise_floor
            stat, p = wilcoxon(order_divs, noise_floors, alternative="greater",
                               zero_method="zsplit")
            significant = bool(p < 0.05 and out["order_divergence_median"] > out["noise_floor_median"])
            out.update({
                "status": "passed" if significant else "failed",
                "wilcoxon_stat": float(stat), "p_value": float(p),
                "significant": significant, "library": "scipy",
            })
        except Exception as exc:  # noqa: BLE001 — control best-effort
            out.update({"status": "skipped", "reason": f"scipy: {exc}",
                        "p_value": None, "significant": False})
        return out
