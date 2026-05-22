"""The Finance-Path-Dependence scenario — the functional advantage on real
market data: does Kimera's memory track an order-dependent financial quantity
that set-based retrieval structurally cannot?

The memory proofs (permanence, path-depth, order-hysteresis) showed Kimera's
memory is *structurally* different from RAG: it carries the order of experience.
This proof asks the harder, investor-grade question — is that difference
*useful* on real data? — and answers it on the canonical path-dependent
financial quantity: **maximum drawdown**.

Why max drawdown is the right ground truth
==========================================

Max drawdown (the largest peak-to-trough decline of a price path) is
**order-dependent by definition**. Take a set of returns; its sum, mean and
multiset are invariant to order, but its max drawdown is *not* — the same
returns arranged worst-first vs best-first give very different drawdowns. So:

  * a set-based retriever (TF-IDF / dense / BM25 / FAISS) represents a sequence
    of return-events by the *multiset* of events; its representation is
    identical for the true order and any shuffle (order divergence ≡ 0). It is
    **structurally blind** to the order that determines drawdown.
  * Kimera's memory is path-dependent (order-hysteresis proof). The open,
    falsifiable question: does its representation-divergence between the true
    order and a shuffle **track the real Δ max-drawdown**?

Pre-registered headline
=======================

    drawdown_tracking_rho =
        Spearman( kimera_state_divergence(true, shuffle),
                  | maxdrawdown(true) − maxdrawdown(shuffle) | )

over real-market return windows × shuffles. VALIDATED iff rho > 0 with p < 0.05
— Kimera's manifold deformation tracks the order-dependent drawdown that a
set-based representation cannot see (the RAG side carries divergence ≡ 0,
demonstrated). REFUTED iff rho ≤ 0 — Kimera sees order (hysteresis) but its
text encoding does not capture the *numeric* path that drawdown needs; an honest
construction brief (finance needs a numeric channel), not an artefact.

The data is real (FRED market series); the ground truth (max drawdown) is
computed, not labelled; the order effect is isolated (true vs shuffle hold the
return multiset constant), so this is not rigged toward Kimera.
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
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest
from ophamin.seeing.substrate.field_catalog import FieldContract, ScenarioFieldContract
from ophamin.seeing.substrate.observables import jaccard as _toolbox_jaccard
from ophamin.seeing.substrate.observables import prime_set as _toolbox_prime_set


class FinancePathDependenceScenario(Scenario):
    """Does Kimera's memory track order-dependent max-drawdown where RAG cannot?

    Construct with real return windows (each a tuple of period returns); call
    ``run(adapter)`` with a live :class:`KimeraAdapter` in batch mode. For each
    window it runs the true order and ``n_shuffles`` shuffles (each a fresh
    accumulation trajectory), reads Kimera's final-state divergence, and
    correlates it with the real Δ max-drawdown. ``run()`` is fully overridden;
    ``score()`` is unreachable.
    """

    name = "finance-path-dependence"
    tier = Tier.SCIENTIFIC
    family = "memory"
    scope = "comparison"
    runner_path = "examples/run_finance_path_dependence.py"
    target = "entity"
    goal = (
        "Show the functional advantage on real market data: Kimera's memory "
        "tracks an order-dependent financial quantity (max drawdown) that "
        "set-based retrieval is structurally blind to."
    )
    explanation = (
        "Max drawdown is order-dependent by definition: the same return multiset "
        "in a different order has a different drawdown, so a set-based retriever "
        "(whose representation is order-invariant) cannot represent it (order "
        "divergence ≡ 0). The order-hysteresis proof showed Kimera's memory IS "
        "order-sensitive; this asks whether that sensitivity TRACKS the real "
        "drawdown. Per real-market return window × shuffle: ΔMDD = |maxdrawdown"
        "(true) − maxdrawdown(shuffle)|; kimera_state_divergence = relative "
        "distance of Kimera's final manifold state (coupling/order/mass) between "
        "the orders. drawdown_tracking_rho = Spearman(kimera_state_divergence, "
        "ΔMDD). > 0 + significant ⇒ Kimera's memory carries the path-information "
        "a real financial risk metric needs, where RAG carries zero. ≤ 0 ⇒ "
        "Kimera's text encoding misses the numeric path (a finance construction "
        "brief)."
    )
    method = "drawdown_order_tracking_spearman_vs_order_invariant_baseline"
    falsification_consequence = (
        "Kimera's manifold-state divergence between return orderings does NOT "
        "track the real Δ max-drawdown — its memory is order-sensitive (per the "
        "hysteresis proof) but its text encoding does not capture the numeric "
        "price path that drawdown depends on. The finance construction brief: a "
        "numeric channel is needed. Not a measurement artefact."
    )

    def __init__(
        self,
        *,
        return_windows: tuple[tuple[float, ...], ...],
        n_shuffles: int = 3,
        shuffle_seed: int = 7,
        min_points: int = 8,
        series_label: str = "fred-market-series",
    ) -> None:
        if not return_windows:
            raise ValueError("return_windows must be non-empty")
        for w in return_windows:
            if len(w) < 3:
                raise ValueError("each return window needs >= 3 periods")
        if n_shuffles < 1:
            raise ValueError("n_shuffles must be >= 1")
        self.return_windows = tuple(tuple(float(x) for x in w) for w in return_windows)
        self.n_shuffles = int(n_shuffles)
        self.shuffle_seed = int(shuffle_seed)
        self.min_points = int(min_points)
        self.series_label = str(series_label)
        # true + n_shuffles batches per window, len(window) cycles each
        self.n_cycles = sum((1 + self.n_shuffles) * len(w) for w in self.return_windows)

    # ----------------------------------------------------- finance math ------

    @staticmethod
    def _max_drawdown(returns: tuple[float, ...]) -> float:
        """|maximum drawdown| of the price path implied by ``returns``.

        Order-dependent by construction: a function of the *path*, not the set.
        """
        import numpy as np

        r = np.asarray(returns, dtype=float)
        prices = np.cumprod(1.0 + r)
        peak = np.maximum.accumulate(prices)
        dd = prices / peak - 1.0
        return float(abs(dd.min())) if dd.size else 0.0

    @staticmethod
    def _render_event(i: int, r: float) -> str:
        """A single return rendered as a substrate-ingestible event.

        Numeric-forward (the return value is the signal; per WL9 numerics drive
        the substrate's prime variance) with minimal boilerplate.
        """
        return f"market day {i + 1}: return {r:+.4f}"

    # ----------------------------------------------------- extraction --------

    @staticmethod
    def _state_vector(result: CycleResult) -> dict[str, float] | None:
        if not result.success:
            return None
        raw = result.raw or {}

        def f(key: str) -> float | None:
            v = raw.get(key)
            return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None

        out: dict[str, float] = {}
        for label, key in (
            ("coupling", "arachne_web_coupling_frobenius"),
            ("order_param", "arachne_web_order_parameter"),
            ("mass", "knowledge_mass"),
        ):
            v = f(key)
            if v is not None:
                out[label] = v
        return out or None

    @staticmethod
    def _state_divergence(a: dict[str, float] | None, b: dict[str, float] | None) -> float | None:
        if not a or not b:
            return None
        diffs: list[float] = []
        for k in ("coupling", "order_param", "mass"):
            if k in a and k in b:
                denom = abs(a[k]) + abs(b[k])
                diffs.append(abs(a[k] - b[k]) / denom if denom else 0.0)
        return float(mean(diffs)) if diffs else None

    # prime_set / jaccard are the shared toolbox canonicals.
    _prime_set = staticmethod(_toolbox_prime_set)
    _jaccard = staticmethod(_toolbox_jaccard)

    # --------------------------------------------------------------- claim ---

    def field_contract(self) -> ScenarioFieldContract:
        """Seatbelt: the manifold-state observables are load-bearing here."""
        return ScenarioFieldContract(
            scenario_name=self.name,
            contracts=(
                FieldContract("arachne_web_coupling_frobenius", required=True),
                FieldContract("knowledge_mass", required=False),
                FieldContract("arachne_web_order_parameter", required=False),
                FieldContract("prime_chain", required=False),
            ),
        )

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                "On real market returns, Kimera's memory tracks the "
                "order-dependent maximum drawdown that set-based retrieval is "
                "structurally blind to: drawdown_tracking_rho = "
                "Spearman(kimera_state_divergence(true, shuffle), |maxdrawdown"
                "(true) − maxdrawdown(shuffle)|) > 0, while the RAG aggregate "
                "representation divergence between orderings is ≡ 0."
            ),
            operationalization=(
                f"For {len(self.return_windows)} real-market return windows "
                f"(len {len(self.return_windows[0])}), run the true order and "
                f"{self.n_shuffles} shuffles through Kimera entity·batch (each a "
                "fresh trajectory). Per (window, shuffle): ΔMDD = |MDD(true) − "
                "MDD(shuffle)| (order-dependent ground truth); "
                "kimera_state_divergence = relative distance of the final "
                "manifold state (coupling/order/mass). drawdown_tracking_rho = "
                "Spearman over all pairs. RAG contrast: mean-pooled TF-IDF "
                "representation divergence between orderings (≡ 0, same "
                "multiset). VALIDATED iff rho > 0 with p < 0.05."
            ),
            threshold=Threshold(
                metric="drawdown_tracking_rho", comparator=">", value=0.0,
                units="spearman_rho",
            ),
            h0=(
                "H0: drawdown_tracking_rho <= 0 — Kimera's representation does "
                "not track order-dependent drawdown; its text encoding misses "
                "the numeric path (like a set-based retriever)"
            ),
            h1=(
                "H1: drawdown_tracking_rho > 0 — Kimera's manifold deformation "
                "tracks the real order-dependent drawdown that set-based "
                "retrieval cannot represent"
            ),
        )

    def analysis_plan(self) -> str:
        return (
            f"Run {len(self.return_windows)} real return windows × (1 true + "
            f"{self.n_shuffles} shuffles) through Kimera entity·batch. Per pair "
            "compute ΔMDD (order-dependent ground truth) and Kimera "
            "state-divergence (final manifold state). Headline: "
            "drawdown_tracking_rho = Spearman(state_divergence, ΔMDD). "
            f"INCONCLUSIVE if fewer than {self.min_points} valid pairs or rho>0 "
            "is not significant; VALIDATED iff rho > 0 (p<0.05); REFUTED iff "
            "rho <= 0. RAG mean-pooled representation divergence (≡ 0) is the "
            "structural contrast. Per-pair series + binary prime-address "
            "order-divergence are evidence."
        )

    def score(self, cycle_results: list[CycleResult], records: list[Any]) -> ScenarioScore:
        raise NotImplementedError(
            "FinancePathDependenceScenario uses a custom run() loop; "
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
                "FinancePathDependenceScenario.run needs a live substrate "
                "adapter in batch mode (each order is one trajectory).")

        try:
            from scipy.stats import spearmanr
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"scipy required for the Spearman headline: {exc}")

        pairs: list[dict[str, Any]] = []
        state_divs: list[float] = []
        dmdds: list[float] = []
        prime_divs: list[float] = []
        rag_divs: list[float] = []

        for wi, returns in enumerate(self.return_windows):
            true_events = [self._render_event(i, r) for i, r in enumerate(returns)]
            res_true = substrate.run_batch(true_events)
            if wi == 0:
                self._enforce_field_contract(res_true)  # seatbelt: once, up front
            state_true = self._state_vector(res_true[-1]) if res_true else None
            primes_true = self._prime_set(res_true[-1]) if res_true else None
            mdd_true = self._max_drawdown(returns)

            for si in range(self.n_shuffles):
                shuffled = list(returns)
                # deterministic per (window, shuffle); ensure a real reorder
                r2 = random.Random(self.shuffle_seed + wi * 101 + si + 1)
                r2.shuffle(shuffled)
                if tuple(shuffled) == returns and len(returns) > 1:
                    shuffled = list(reversed(returns))
                shuf_events = [self._render_event(i, r) for i, r in enumerate(shuffled)]
                res_shuf = substrate.run_batch(shuf_events)
                state_shuf = self._state_vector(res_shuf[-1]) if res_shuf else None
                primes_shuf = self._prime_set(res_shuf[-1]) if res_shuf else None

                dmdd = abs(mdd_true - self._max_drawdown(tuple(shuffled)))
                ksd = self._state_divergence(state_true, state_shuf)
                kpd = (
                    1.0 - self._jaccard(primes_true, primes_shuf)
                    if (primes_true is not None and primes_shuf is not None) else None
                )
                rag = bag_representation_divergence(true_events, shuf_events)
                rag_divs.append(rag)
                rec = {
                    "window": wi, "shuffle": si,
                    "delta_max_drawdown": round(dmdd, 6),
                    "kimera_state_divergence": (round(ksd, 6) if ksd is not None else None),
                    "kimera_prime_divergence": (round(kpd, 6) if kpd is not None else None),
                    "rag_representation_divergence": round(rag, 8),
                    "mdd_true": round(mdd_true, 6),
                }
                pairs.append(rec)
                if ksd is not None:
                    state_divs.append(ksd)
                    dmdds.append(dmdd)
                if kpd is not None:
                    prime_divs.append(kpd)

        n_points = len(state_divs)
        rho: float | None = None
        p_value: float | None = None
        if n_points >= 4 and len(set(dmdds)) > 1 and len(set(state_divs)) > 1:
            rr, pp = spearmanr(state_divs, dmdds, alternative="greater")
            rho = float(rr) if rr == rr else None  # guard NaN
            p_value = float(pp) if pp == pp else None

        observed = rho if rho is not None else 0.0
        significant = bool(p_value is not None and p_value < 0.05 and observed > 0)
        inconclusive = (
            n_points < self.min_points
            or rho is None
            or (observed > 0 and not significant)
        )

        rag_mean = mean(rag_divs) if rag_divs else 0.0
        prime_div_mean = mean(prime_divs) if prime_divs else 0.0
        state_div_mean = mean(state_divs) if state_divs else 0.0

        config = {
            "scenario": self.name, "scope": self.scope,
            "n_windows": len(self.return_windows),
            "window_len": len(self.return_windows[0]),
            "n_shuffles": self.n_shuffles, "shuffle_seed": self.shuffle_seed,
        }
        dataset = DatasetRef(
            name="fred-market-return-windows",
            content_hash=content_hash({"windows": [list(w) for w in self.return_windows]}),
            n_records=self.n_cycles,
            source=self.series_label,
            kind="real-market-returns+order-permutation",
        )
        prereg = PreRegistration(
            config_hash=content_hash(config), data_hash=dataset.content_hash,
            analysis_plan=self.analysis_plan(),
        )
        claim = self.build_claim()

        reasoning = (
            f"drawdown_tracking_rho {observed:+.4f} (p={p_value}) over {n_points} "
            f"real-market window×shuffle pairs: Kimera state-divergence vs "
            f"|ΔMDD| (Spearman). RAG aggregate representation divergence "
            f"{rag_mean:.6f} (order-invariant — carries zero drawdown order-"
            f"information). Kimera mean state-divergence {state_div_mean:.4f}, "
            f"prime-address order-divergence {prime_div_mean:.4f}; series "
            f"{self.series_label}"
        )
        if inconclusive:
            reasoning += (
                "; INCONCLUSIVE — "
                + ("too few valid pairs" if n_points < self.min_points
                   else "rho>0 not statistically significant")
            )
        elif observed <= 0:
            reasoning += (
                "; REFUTED — Kimera's representation does not track order-"
                "dependent drawdown (text encoding misses the numeric path)"
            )

        verdict = Verdict.decide(
            observed=observed, threshold=claim.threshold,
            inconclusive=inconclusive, reasoning=reasoning,
        )

        evidence = [
            PillarEvidence(
                pillar="O.comparison.finance_path_dependence",
                statistic_name="drawdown_tracking_rho",
                statistic_value=observed,
                library="ophamin",
                library_version=__version__,
                cross_check="passed" if significant else ("skipped" if inconclusive else "failed"),
                p_value=p_value,
                detail={
                    "scope": "comparison",
                    "drawdown_tracking_rho": rho,
                    "spearman_p_value": p_value,
                    "n_pairs": n_points,
                    "kimera_state_divergence_mean": state_div_mean,
                    "kimera_prime_divergence_mean": prime_div_mean,
                    "rag_representation_divergence_mean": rag_mean,
                    "series_label": self.series_label,
                    "n_windows": len(self.return_windows),
                    "window_len": len(self.return_windows[0]),
                    "n_shuffles": self.n_shuffles,
                    "per_pair": pairs,
                    "interpretation": (
                        "rho>0 + significant = Kimera's memory tracks the order-"
                        "dependent drawdown a real risk metric needs, where a "
                        "set-based retriever's representation is order-invariant "
                        "(divergence 0) and carries none of it. rho<=0 = Kimera "
                        "sees order (hysteresis) but its text encoding misses the "
                        "numeric price path — a finance numeric-channel "
                        "construction brief."
                    ),
                    "grounding_anchor": (
                        "max drawdown is order-dependent by definition (same "
                        "return multiset, different order → different drawdown); "
                        "FRED real-market series; set-based representation order-"
                        "invariance demonstrated via mean-pooled TF-IDF."
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
