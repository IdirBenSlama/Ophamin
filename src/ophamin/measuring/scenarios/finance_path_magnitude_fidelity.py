"""Finance path-magnitude fidelity — the fair, GRADED Kimera-vs-baseline test.

This is the test the whole observatory was meant to run: not "does Kimera tell
two orderings apart" (binary; a metric artifact, as the earlier
finance-history-discrimination proof was shown to be), but **does Kimera's
representation-distance SCALE with the real, graded path-property the orderings
encode** — here, ``|Δ max-drawdown|`` between same-multiset return histories.

A genuine path-memory grades: more-different paths → more-different
representations. A binary order-detector saturates (every distance ~1.0) and so
carries no graded signal — it scores ~0 on this test by construction. That is the
honest discriminator between "real hysteretic memory" and "string-hashing that
differs on reorder".

Fairness (the bar Kimera must clear, established empirically in
``diagnostics/path_magnitude_bar.py`` on real FRED data):

  * order-blind floor (mean-pooled TF-IDF) → graded fidelity ≈ 0 (no order info).
  * order-aware bar (consecutive-event shingle) → the graded fidelity a STANDARD
    order-aware retriever already achieves (~0.04 on SP500 — drawdown is a
    cumulative-min path functional that generic representations barely capture).

Kimera is **VALIDATED** iff its prime-distance grades ``|Δ max-drawdown|`` with a
Spearman fidelity that exceeds the order-aware bar by a pre-registered margin
(``graded_fidelity_advantage >= 0.20``); **REFUTED** if it does not — i.e. its
prime-address is a saturated binary detector, not a graded path-memory.

Matched metric: BOTH sides are scored with ``graded_fidelity`` (Spearman of
pairwise representation-distance vs ``|Δ max-drawdown|``). Kimera's
representation-distance is ``1 − Jaccard(prime_chain)`` (the same prime-set
distance the prior scenarios used); the baselines are the order-aware shingle and
the order-blind mean-pool on the same event sequences. No metric mismatch — the
flaw that inflated the earlier "advantage 1.0" is removed by construction.

``run()`` needs a live substrate (Kimera) in batch mode; ``score()`` is
unreachable. The baseline bar runs without Kimera via the diagnostic above.
"""

from __future__ import annotations

import random
from typing import Any

from ophamin import __version__
from ophamin.comparing.provenance import ProvenanceGraph
from ophamin.comparing.provenance.lineage import (
    _ophamin_project_root,
    capture_git_commit,
)
from ophamin.comparing.retrieval_baseline import (
    bag_representation_divergence,
    graded_fidelity,
    ordered_representation_divergence,
)
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
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, Scenario, ScenarioScore, Tier
from ophamin.measuring.scenarios.finance_path_dependence import (
    FinancePathDependenceScenario,
)
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest
from ophamin.seeing.substrate.field_catalog import FieldContract, ScenarioFieldContract
from ophamin.seeing.substrate.observables import jaccard

_max_drawdown = FinancePathDependenceScenario._max_drawdown
_render_event = FinancePathDependenceScenario._render_event
_prime_set = FinancePathDependenceScenario._prime_set


def _content_events(arr: tuple[float, ...]) -> list[str]:
    """One token per return, in order, with NO position tag — so the only signal
    the baselines can use is the ORDER of the multiset (matches the diagnostic)."""
    return [f"r{r:+.5f}" for r in arr]


class FinancePathMagnitudeFidelityScenario(Scenario):
    """Does Kimera's prime-distance GRADE |Δ max-drawdown|, beating order-aware retrieval?"""

    name = "finance-path-magnitude-fidelity"
    tier = Tier.SCIENTIFIC
    family = "memory"
    scope = "comparison"
    runner_path = "examples/run_finance_path_magnitude_fidelity.py"
    target = "entity"
    goal = (
        "Establish whether Kimera's path-memory is GRADED: does its "
        "representation-distance between same-multiset return histories scale "
        "with their real |Δ max-drawdown|, better than a standard order-aware "
        "retriever — or does it saturate (a binary order-detector)?"
    )
    explanation = (
        "For each real return multiset, many orderings are generated spanning a "
        "range of max-drawdowns. Every representation scores the SAME way: "
        "graded_fidelity = Spearman(pairwise representation-distance, "
        "|Δ max-drawdown|). Kimera distance = 1 − Jaccard(prime_chain); the "
        "order-aware bar = consecutive-event shingle cosine; the order-blind "
        "floor = mean-pooled TF-IDF (≈0). VALIDATED iff Kimera grades drawdown "
        "ABOVE the order-aware bar by the pre-registered margin; a saturated "
        "prime-distance scores ~0 and is REFUTED. The matched metric removes the "
        "metric-mismatch that inflated the earlier binary 'advantage'."
    )
    method = "graded_fidelity_advantage_over_order_aware_baseline"
    falsification_consequence = (
        "Kimera's prime-distance does not grade |Δ max-drawdown| better than a "
        "generic order-aware retriever (advantage <= margin) — its path-memory is "
        "a saturated binary order-detector, not a graded magnitude-bearing "
        "representation. Refutes the graded path-memory claim."
    )

    def __init__(
        self,
        *,
        return_windows: tuple[tuple[float, ...], ...],
        n_orderings: int = 24,
        advantage_margin: float = 0.20,
        min_windows: int = 4,
        series_label: str = "fred-market-series",
        seed: int = 0,
    ) -> None:
        if not return_windows:
            raise ValueError("return_windows must be non-empty")
        for w in return_windows:
            if len(w) < 4:
                raise ValueError("each return window needs >= 4 periods")
        if n_orderings < 6:
            raise ValueError("n_orderings must be >= 6 for a stable rank correlation")
        if not 0.0 < advantage_margin < 1.0:
            raise ValueError("advantage_margin must be in (0, 1)")
        self.return_windows = tuple(tuple(float(x) for x in w) for w in return_windows)
        self.n_orderings = int(n_orderings)
        self.advantage_margin = float(advantage_margin)
        self.min_windows = int(min_windows)
        self.series_label = str(series_label)
        self.seed = int(seed)
        self.n_cycles = sum(self.n_orderings * len(w) for w in self.return_windows)

    def _orderings(self, multiset: tuple[float, ...]) -> list[tuple[float, ...]]:
        """Diverse orderings spanning drawdowns: the two sorted extremes + shuffles."""
        variants = [tuple(sorted(multiset)), tuple(sorted(multiset, reverse=True))]
        for s in range(self.n_orderings):
            a = list(multiset)
            random.Random(self.seed + s).shuffle(a)
            variants.append(tuple(a))
        return list(dict.fromkeys(variants))

    def field_contract(self) -> ScenarioFieldContract:
        return ScenarioFieldContract(
            scenario_name=self.name,
            contracts=(FieldContract("prime_chain", required=True),),
        )

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                "Kimera's representation-distance (1 − Jaccard of prime_chain) "
                "between same-multiset return histories GRADES their real "
                "|Δ max-drawdown| (Spearman fidelity) better than a standard "
                "order-aware retriever, by a margin: graded_fidelity_advantage = "
                f"fidelity(kimera) − fidelity(order_aware) >= {self.advantage_margin}."
            ),
            operationalization=(
                f"For {len(self.return_windows)} real return multisets, generate "
                f"{self.n_orderings}+2 orderings spanning drawdowns; score each "
                "representation by Spearman(pairwise distance, |Δ max-drawdown|). "
                "Headline = mean over windows of fidelity(kimera) − "
                "fidelity(order_aware shingle). Order-blind mean-pool reported as "
                "the ~0 floor."
            ),
            threshold=Threshold(
                metric="graded_fidelity_advantage",
                comparator=">=",
                value=self.advantage_margin,
                units="spearman_rho",
            ),
            h0=(
                "H0: advantage < margin — Kimera does not grade drawdown better "
                "than generic order-aware retrieval (saturated binary detector)."
            ),
            h1=(
                "H1: advantage >= margin — Kimera's prime-distance carries graded "
                "path-magnitude that generic order-aware retrieval does not."
            ),
        )

    def analysis_plan(self) -> str:
        return (
            f"For each of {len(self.return_windows)} real multisets, build "
            f"{self.n_orderings}+2 orderings; run each through Kimera entity·batch; "
            "compute pairwise kimera_distance = 1 − Jaccard(prime_chain), "
            "order_aware = shingle cosine, order_blind = mean-pool. "
            "graded_fidelity = Spearman(distance, |Δ max-drawdown|) per method per "
            "window. Headline = mean(fid_kimera − fid_order_aware). "
            f"INCONCLUSIVE if fewer than {self.min_windows} windows yield primes "
            "for all orderings; VALIDATED iff advantage >= margin."
        )

    def score(self, cycle_results: list[CycleResult], records: list[Any]) -> ScenarioScore:
        raise NotImplementedError(
            "FinancePathMagnitudeFidelityScenario uses a custom run() loop; "
            "score() is unreachable.")

    def run(
        self,
        substrate: SubstrateUnderTest | None = None,
        *,
        data_root: object = None,
        sign_key: bytes = DEFAULT_SIGN_KEY,
    ) -> EmpiricalProofRecord:
        if substrate is None:
            raise ValueError(
                "FinancePathMagnitudeFidelityScenario.run needs a live substrate "
                "adapter in batch mode.")

        from itertools import combinations

        per_window: list[dict[str, Any]] = []
        fid_kimera: list[float] = []
        fid_order: list[float] = []
        fid_blind: list[float] = []

        for wi, ms in enumerate(self.return_windows):
            variants = self._orderings(ms)
            dds = [_max_drawdown(v) for v in variants]
            prime_sets: list[Any] = []
            for v in variants:
                events = [_render_event(i, r) for i, r in enumerate(v)]
                res = substrate.run_batch(events)
                if wi == 0 and v is variants[0]:
                    self._enforce_field_contract(res)  # seatbelt, once
                prime_sets.append(_prime_set(res[-1]) if res else None)
            content = [_content_events(v) for v in variants]

            k_d: list[float] = []
            o_d: list[float] = []
            b_d: list[float] = []
            gt: list[float] = []
            ok = True
            for i, j in combinations(range(len(variants)), 2):
                if prime_sets[i] is None or prime_sets[j] is None:
                    ok = False
                    break
                gt.append(abs(dds[i] - dds[j]))
                k_d.append(1.0 - jaccard(prime_sets[i], prime_sets[j]))
                o_d.append(ordered_representation_divergence(content[i], content[j]))
                b_d.append(bag_representation_divergence(content[i], content[j]))
            if not ok or len(gt) < 3:
                per_window.append({"window": wi, "gap": True})
                continue
            fk = graded_fidelity(k_d, gt)
            fo = graded_fidelity(o_d, gt)
            fb = graded_fidelity(b_d, gt)
            fid_kimera.append(fk)
            fid_order.append(fo)
            fid_blind.append(fb)
            per_window.append({
                "window": wi,
                "n_orderings": len(variants),
                "n_pairs": len(gt),
                "fidelity_kimera": round(fk, 4),
                "fidelity_order_aware": round(fo, 4),
                "fidelity_order_blind": round(fb, 4),
                "gap": False,
            })

        n_ok = len(fid_kimera)
        if n_ok < self.min_windows:
            advantage = 0.0
            inconclusive = True
            reasoning = (
                f"only {n_ok}/{len(self.return_windows)} windows yielded primes "
                f"for all orderings (need {self.min_windows})."
            )
        else:
            mean_k = sum(fid_kimera) / n_ok
            mean_o = sum(fid_order) / n_ok
            advantage = mean_k - mean_o
            inconclusive = False
            reasoning = (
                f"graded fidelity — kimera={mean_k:.3f}, order-aware bar={mean_o:.3f}, "
                f"order-blind floor={sum(fid_blind) / n_ok:.3f}; "
                f"advantage={advantage:.3f} vs margin {self.advantage_margin}."
            )

        claim = self.build_claim()
        verdict = Verdict.decide(
            advantage, claim.threshold, inconclusive=inconclusive, reasoning=reasoning,
        )
        dataset = DatasetRef(
            name=self.series_label, content_hash=content_hash(self.return_windows),
            n_records=len(self.return_windows), source="fred", kind="market-returns",
        )
        prereg = PreRegistration(
            config_hash=content_hash({
                "scenario": self.name, "n_orderings": self.n_orderings,
                "advantage_margin": self.advantage_margin, "seed": self.seed,
            }),
            data_hash=dataset.content_hash,
            analysis_plan=self.analysis_plan(),
        )
        evidence = [
            PillarEvidence(
                pillar="graded-fidelity", statistic_name="graded_fidelity_advantage",
                statistic_value=round(advantage, 6), library="scipy",
                library_version="spearmanr", detail={"per_window": per_window},
            ),
        ]
        substrate_commit = ""
        getter = getattr(substrate, "git_commit", None)
        if callable(getter):
            try:
                substrate_commit = str(getter() or "")[:12]
            except Exception:  # noqa: BLE001 — commit is best-effort metadata
                substrate_commit = ""
        prov = ProvenanceGraph()
        prov.agent("kimera-swm", role="substrate_under_test")
        record = EmpiricalProofRecord(
            claim=claim, preregistration=prereg, datasets=[dataset],
            substrate_name=getattr(substrate, "name", "kimera-swm"),
            substrate_git_commit=substrate_commit,
            evidence=evidence, verdict=verdict,
            reproduction=Reproduction(command=self._build_reproduction_command()),
            provenance=prov.to_prov_json(),
            ophamin_version=__version__,
            ophamin_git_commit=capture_git_commit(_ophamin_project_root()),
        )
        record.sign(sign_key)
        return record
