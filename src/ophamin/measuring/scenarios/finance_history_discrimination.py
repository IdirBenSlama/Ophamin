"""The Finance-History-Discrimination scenario — the honest positive capability
on real market data: Kimera separates real-outcome-different histories that a
set-based retriever conflates.

This is the counterpart to ``finance-path-dependence`` (MEM4) and the
drawdown-gradedness diagnostic, which together established the *limit*: Kimera's
prime-address is a **saturated binary order-detector**, not a magnitude tracker
— it does NOT grade representations by max-drawdown (Spearman ρ ≈ 0, ns, even at
extreme controlled spread). This scenario establishes the *capability* the same
finding implies: because the address saturates, Kimera **distinguishes** any two
arrangements of the same event-multiset, while a set-based retriever (TF-IDF /
dense / BM25 / FAISS) represents them identically (its representation is a
function of the multiset alone).

The grounding that makes this non-trivial: the two arrangements are not arbitrary
— they are the **minimum-drawdown** and **maximum-drawdown** orderings of the
same real return multiset, i.e. genuinely different real-risk situations (a
portfolio that rose-then-fell vs one that crashed-then-recovered — the same
trades, opposite risk experience). A retriever that conflates them is blind to a
real, consequential difference; Kimera is not.

Pre-registered headline
=======================

    history_separation_advantage =
        mean( kimera_prime_distance(min_DD_order, max_DD_order) )
      − mean( rag_representation_distance(min_DD_order, max_DD_order) )

over real-market return multisets. VALIDATED iff > 0 with Kimera separating
every outcome-different pair (rate = 1.0) and the RAG side conflating them
(≈ 0) — Kimera resolves real-risk-different histories a set-based retriever
cannot. The claim is explicitly **discrimination, not magnitude regression**:
the gradedness limit is reported, not hidden.
"""

from __future__ import annotations

import random
from statistics import mean
from typing import Any

from ophamin import __version__
from ophamin.comparing.provenance import ProvenanceGraph
from ophamin.comparing.provenance.lineage import (
    _ophamin_project_root,
    capture_git_commit,
)
from ophamin.comparing.retrieval_baseline import bag_representation_divergence
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
from ophamin.measuring.scenarios.finance_path_dependence import (
    FinancePathDependenceScenario,
)
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest

_max_drawdown = FinancePathDependenceScenario._max_drawdown
_render_event = FinancePathDependenceScenario._render_event
_prime_set = FinancePathDependenceScenario._prime_set


class FinanceHistoryDiscriminationScenario(Scenario):
    """Kimera separates real-risk-different same-set histories; RAG conflates them.

    Construct with real return multisets; ``run(adapter)`` builds the min- and
    max-drawdown ordering of each (same multiset, opposite real risk), runs both
    through Kimera (fresh trajectories), and contrasts Kimera's representation
    separation with the order-invariant RAG baseline. ``run()`` is overridden;
    ``score()`` is unreachable.
    """

    name = "finance-history-discrimination"
    tier = Tier.SCIENTIFIC
    family = "memory"
    scope = "comparison"
    runner_path = "examples/run_finance_history_discrimination.py"
    target = "entity"
    goal = (
        "Establish the honest positive capability on real market data: Kimera "
        "distinguishes two arrangements of the same return multiset that have "
        "genuinely different real risk (min vs max drawdown), where a set-based "
        "retriever represents them identically."
    )
    explanation = (
        "MEM4 + the drawdown-gradedness diagnostic established the limit: "
        "Kimera's prime-address is a saturated binary order-detector, not a "
        "magnitude tracker (no gradedness by drawdown). This scenario "
        "establishes the capability that implies: Kimera SEPARATES any two "
        "same-multiset arrangements (prime-address distance ~1) while a "
        "set-based retriever conflates them (distance 0, representation is a "
        "function of the multiset). The grounding: the two arrangements are the "
        "min-drawdown and max-drawdown orderings of the same real returns — "
        "genuinely different risk situations. history_separation_advantage = "
        "mean(kimera_prime_distance) − mean(rag_distance). The claim is "
        "discrimination, not magnitude regression; the gradedness limit is "
        "reported, not hidden."
    )
    method = "min_vs_max_drawdown_order_separation_vs_order_invariant_baseline"
    falsification_consequence = (
        "Kimera conflates the min-drawdown and max-drawdown orderings of the "
        "same return multiset (representation distance ~0), i.e. it cannot "
        "distinguish real-risk-different histories any better than a set-based "
        "retriever. Would refute the discrimination capability."
    )

    def __init__(
        self,
        *,
        return_windows: tuple[tuple[float, ...], ...],
        search_shuffles: int = 300,
        separation_threshold: float = 0.5,
        min_windows: int = 4,
        series_label: str = "fred-market-series",
    ) -> None:
        if not return_windows:
            raise ValueError("return_windows must be non-empty")
        for w in return_windows:
            if len(w) < 3:
                raise ValueError("each return window needs >= 3 periods")
        self.return_windows = tuple(tuple(float(x) for x in w) for w in return_windows)
        self.search_shuffles = int(search_shuffles)
        self.separation_threshold = float(separation_threshold)
        self.min_windows = int(min_windows)
        self.series_label = str(series_label)
        self.n_cycles = sum(2 * len(w) for w in self.return_windows)

    # --------------------------------------------------- arrangement search --

    def _min_max_dd_orderings(
        self, multiset: tuple[float, ...]
    ) -> tuple[tuple[float, ...], float, tuple[float, ...], float]:
        """Find the min- and max-drawdown ordering of ``multiset``.

        Searches random shuffles plus the two sorted extremes (gains-first
        tends to minimise drawdown; losses-first tends to maximise it).
        """
        cands: dict[tuple[float, ...], float] = {}
        cands[tuple(sorted(multiset, reverse=True))] = _max_drawdown(tuple(sorted(multiset, reverse=True)))
        cands[tuple(sorted(multiset))] = _max_drawdown(tuple(sorted(multiset)))
        for s in range(self.search_shuffles):
            a = list(multiset)
            random.Random(s).shuffle(a)
            t = tuple(a)
            if t not in cands:
                cands[t] = _max_drawdown(t)
        lo = min(cands.items(), key=lambda kv: kv[1])
        hi = max(cands.items(), key=lambda kv: kv[1])
        return lo[0], lo[1], hi[0], hi[1]

    @staticmethod
    def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
        u = a | b
        return len(a & b) / len(u) if u else 1.0

    # --------------------------------------------------------------- claim ---

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                "Kimera distinguishes the minimum-drawdown and maximum-drawdown "
                "orderings of the same real return multiset (genuinely different "
                "risk, identical trade-set), where a set-based retriever "
                "represents them identically: history_separation_advantage = "
                "mean(kimera_prime_distance) − mean(rag_representation_distance) "
                "> 0, with Kimera separating every pair and the RAG side "
                "conflating every pair."
            ),
            operationalization=(
                f"For {len(self.return_windows)} real-market return multisets, "
                "find the min-DD and max-DD ordering (search of "
                f"{self.search_shuffles} shuffles + sorted extremes). Run both "
                "through Kimera entity·batch (fresh trajectories). "
                "kimera_prime_distance = 1 − Jaccard(prime_chain). "
                "rag_representation_distance = mean-pooled TF-IDF divergence "
                "(≈ 0, same multiset). VALIDATED iff advantage > 0 with "
                f"separation rate 1.0 (each kimera_prime_distance ≥ "
                f"{self.separation_threshold}, each rag ≈ 0)."
            ),
            threshold=Threshold(
                metric="history_separation_advantage", comparator=">", value=0.0,
                units="representation_distance",
            ),
            h0=(
                "H0: advantage <= 0 — Kimera conflates the min-DD and max-DD "
                "orderings no better than a set-based retriever"
            ),
            h1=(
                "H1: advantage > 0 — Kimera separates real-risk-different "
                "same-set histories that a set-based retriever conflates"
            ),
        )

    def analysis_plan(self) -> str:
        return (
            f"For {len(self.return_windows)} real return multisets, build the "
            "min-DD and max-DD ordering; run both through Kimera entity·batch. "
            "kimera_prime_distance = 1 − Jaccard(prime_chain); "
            "rag_representation_distance = mean-pooled TF-IDF (≈ 0). Headline: "
            "history_separation_advantage = mean(kimera) − mean(rag). "
            f"INCONCLUSIVE if fewer than {self.min_windows} windows yield a "
            "prime address for both orderings; VALIDATED iff advantage > 0 "
            "(Kimera separates, RAG conflates). The real ΔDD per window is "
            "reported as grounding; the gradedness limit (Kimera does NOT grade "
            "by drawdown magnitude, per MEM4 + diagnostic) is stated, not hidden."
        )

    def score(self, cycle_results: list[CycleResult], records: list[Any]) -> ScenarioScore:
        raise NotImplementedError(
            "FinanceHistoryDiscriminationScenario uses a custom run() loop; "
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
                "FinanceHistoryDiscriminationScenario.run needs a live substrate "
                "adapter in batch mode.")

        per_window: list[dict[str, Any]] = []
        kimera_dists: list[float] = []
        rag_dists: list[float] = []
        delta_dds: list[float] = []
        separated_flags: list[bool] = []

        for wi, ms in enumerate(self.return_windows):
            lo_arr, lo_dd, hi_arr, hi_dd = self._min_max_dd_orderings(ms)
            lo_events = [_render_event(i, r) for i, r in enumerate(lo_arr)]
            hi_events = [_render_event(i, r) for i, r in enumerate(hi_arr)]
            res_lo = substrate.run_batch(lo_events)
            res_hi = substrate.run_batch(hi_events)
            p_lo = _prime_set(res_lo[-1]) if res_lo else None
            p_hi = _prime_set(res_hi[-1]) if res_hi else None
            if p_lo is None or p_hi is None:
                per_window.append({"window": wi, "gap": True})
                continue
            kdist = 1.0 - self._jaccard(p_lo, p_hi)
            rdist = bag_representation_divergence(lo_events, hi_events)
            ddd = abs(hi_dd - lo_dd)
            sep = (kdist >= self.separation_threshold) and (rdist < 0.01)
            kimera_dists.append(kdist)
            rag_dists.append(rdist)
            delta_dds.append(ddd)
            separated_flags.append(sep)
            per_window.append({
                "window": wi,
                "min_drawdown": round(lo_dd, 6),
                "max_drawdown": round(hi_dd, 6),
                "delta_drawdown": round(ddd, 6),
                "kimera_prime_distance": round(kdist, 6),
                "rag_representation_distance": round(rdist, 8),
                "separated": sep,
                "gap": False,
            })

        n = len(kimera_dists)
        k_mean = mean(kimera_dists) if kimera_dists else 0.0
        r_mean = mean(rag_dists) if rag_dists else 0.0
        advantage = k_mean - r_mean
        separation_rate = (sum(separated_flags) / n) if n else 0.0
        delta_dd_mean = mean(delta_dds) if delta_dds else 0.0

        # VALIDATED only if there is real data AND every pair is separated by
        # Kimera while RAG conflates (otherwise the advantage is not the clean
        # capability claim). A positive-but-incomplete result is inconclusive.
        inconclusive = n < self.min_windows or (advantage > 0 and separation_rate < 1.0)

        config = {
            "scenario": self.name, "scope": self.scope,
            "n_windows": len(self.return_windows),
            "search_shuffles": self.search_shuffles,
        }
        dataset = DatasetRef(
            name="fred-market-min-max-drawdown-orderings",
            content_hash=content_hash({"windows": [list(w) for w in self.return_windows]}),
            n_records=self.n_cycles,
            source=self.series_label,
            kind="real-market-returns+min-max-drawdown-orderings",
        )
        prereg = PreRegistration(
            config_hash=content_hash(config), data_hash=dataset.content_hash,
            analysis_plan=self.analysis_plan(),
        )
        claim = self.build_claim()

        reasoning = (
            f"history_separation_advantage {advantage:+.4f} = Kimera prime-"
            f"distance {k_mean:.4f} − RAG distance {r_mean:.6f} over {n} real "
            f"min-DD vs max-DD pairs; separation rate {separation_rate:.2f} "
            f"(Kimera distinguishes real-risk-different same-set histories, RAG "
            f"conflates). Mean real ΔDD {delta_dd_mean:.4f} (the histories Kimera "
            f"separates are genuinely different risk). NOTE: this is "
            f"discrimination, not magnitude — Kimera does NOT grade by drawdown "
            f"(MEM4 ρ=+0.18 ns; diagnostic ρ≈0). Series {self.series_label}"
        )
        if inconclusive:
            reasoning += (
                "; INCONCLUSIVE — "
                + ("too few windows with a prime address" if n < self.min_windows
                   else "Kimera did not separate every outcome-different pair")
            )

        verdict = Verdict.decide(
            observed=advantage, threshold=claim.threshold,
            inconclusive=inconclusive, reasoning=reasoning,
        )

        evidence = [
            PillarEvidence(
                pillar="O.comparison.finance_history_discrimination",
                statistic_name="history_separation_advantage",
                statistic_value=advantage,
                library="ophamin",
                library_version=__version__,
                cross_check="passed" if (n >= self.min_windows and separation_rate >= 1.0) else "skipped",
                p_value=None,
                detail={
                    "scope": "comparison",
                    "history_separation_advantage": advantage,
                    "kimera_prime_distance_mean": k_mean,
                    "rag_representation_distance_mean": r_mean,
                    "separation_rate": separation_rate,
                    "delta_drawdown_mean": delta_dd_mean,
                    "n_windows": n,
                    "per_window": per_window,
                    "series_label": self.series_label,
                    "claim_scope": "discrimination_not_magnitude",
                    "gradedness_limit": (
                        "Kimera does NOT grade representations by drawdown "
                        "magnitude (MEM4 finance-path-dependence ρ=+0.18, p=0.23; "
                        "drawdown-gradedness diagnostic ρ≈0 at extreme controlled "
                        "spread). The prime-address is a saturated binary order-"
                        "detector. This proof is the capability that implies: "
                        "binary discrimination of same-set histories."
                    ),
                    "interpretation": (
                        "advantage>0 + rate 1.0 = Kimera resolves real-risk-"
                        "different histories (min-DD vs max-DD ordering of the "
                        "same trades) that a set-based retriever represents "
                        "identically (distance 0). Useful wherever same-set "
                        "different-order means different real meaning; NOT a "
                        "magnitude-regression claim."
                    ),
                    "grounding_anchor": (
                        "min/max drawdown orderings of the same real FRED return "
                        "multiset are genuinely different risk situations; "
                        "set-based representation order-invariance demonstrated "
                        "(mean-pooled TF-IDF ≈ 0)."
                    ),
                },
            ),
        ]

        prov = ProvenanceGraph()
        a_o = prov.agent("ophamin", role="experimentation_framework", version=__version__)
        a_k = prov.agent("kimera-swm", role="substrate_under_comparison")
        a_r = prov.agent("tfidf-baseline", role="order_invariant_representation")
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
