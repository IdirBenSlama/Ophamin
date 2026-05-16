"""The Rosetta Scaling scenario.

Streams sentence-aligned parallel text (FLORES-200) through Kimera's Rosetta
layer and measures how invariant Rosetta is to language — the
universal-semantic-address promise: every concept, in every language, should
collapse to one canonical address.

Per FLORES-200 sentence group, ``K_max`` languages are sampled (deterministic
seed). The harness asks Rosetta to ``process`` each translation in turn and
records the ``canonical`` string it returns. A group "agrees at K" iff the
first K of its translations all map to a *single* canonical value. Agreement
rates are reported at K ∈ {3, 5, 10, 20, K_max}; the pre-registered threshold
sits at ``primary_k`` (default 10).

Two evidence channels are reported in every proof record:

* canonical-string agreement (the primary, since the canonical key is the
  language-invariant address Rosetta advertises);
* composite-prime agreement (secondary, since the prime carries substrate-state
  stamp evolution that the canonical key does not).

Both are binomial proportions with Wilson 95% CIs.

The Rosetta blueprint promises this invariance "every concept × language ×
modality × arm → ONE deterministic prime"; the active ``UNIVERSAL_REGISTRY`` is
~54 entries — so the run measures whether the registry + the encoder fallback
together honour the promise on whole sentences. A REFUTED verdict (Rosetta is
encoder-fallback-dominated outside the registry) is the framework working.
"""

from __future__ import annotations

import hashlib
import random
from collections import defaultdict
from typing import Any, Iterator

import statsmodels as _statsmodels
from statsmodels.stats.proportion import proportion_confint

from ophamin.seeing.corpus import Corpus, CorpusRecord
from ophamin.measuring.proof import Claim, PillarEvidence, Threshold
from ophamin.measuring.scenarios.base import Scenario, ScenarioScore, Tier
from ophamin.seeing.substrate.base import CycleResult


class RosettaScalingScenario(Scenario):
    """Rosetta universal-semantic-address invariance across N languages."""

    name = "rosetta-scaling"
    tier = Tier.SCIENTIFIC
    family = "rosetta"
    goal = (
        "Test Rosetta's universal-semantic-address promise: every "
        "concept, in every language, should collapse to one canonical."
    )
    explanation = (
        "Kimera's Rosetta layer claims to provide a language-invariant "
        "semantic address — the same concept in English / French / "
        "Arabic / Mandarin should map to the same canonical (and, "
        "downstream, the same prime). This scenario samples K aligned "
        "translations per FLORES-200 sentence group and measures the "
        "fraction of groups whose first K translations all agree on a "
        "single canonical. The threshold (default 80% at K=10) tests "
        "whether the registry + encoder-fallback together honour the "
        "promise on whole sentences."
    )
    method = "all_k_agree_proportion"
    falsification_consequence = (
        "Rosetta is encoder-fallback-dominated outside its ~54-entry "
        "UNIVERSAL_REGISTRY; the universal-semantic-address promise "
        "does not hold for arbitrary input."
    )
    corpus_name = "flores"
    target = "rosetta"

    _K_REPORT = (3, 5, 10, 20, 50)

    def __init__(
        self,
        n_cycles: int = 1000,
        k_max: int = 50,
        primary_k: int = 10,
        agreement_threshold: float = 0.80,
        seed: int = 0,
    ) -> None:
        if k_max < 2:
            raise ValueError(f"k_max must be >= 2, got {k_max}")
        if primary_k < 2 or primary_k > k_max:
            raise ValueError(
                f"primary_k must satisfy 2 <= primary_k <= k_max ({k_max}), "
                f"got {primary_k}"
            )
        if not 0.0 <= agreement_threshold <= 1.0:
            raise ValueError(
                f"agreement_threshold must be in [0, 1], got {agreement_threshold}"
            )
        self.n_cycles = int(n_cycles)
        self.k_max = int(k_max)
        self.primary_k = int(primary_k)
        self.agreement_threshold = float(agreement_threshold)
        self.seed = int(seed)

    # -- harness contract --------------------------------------------------

    def analysis_plan(self) -> str:
        return (
            f"Stream up to {self.n_cycles} single-language translations from "
            f"FLORES-200 ({self.k_max} languages per sentence group, "
            f"deterministically sampled with seed={self.seed}) through Kimera's "
            f"Rosetta '{self.target}' target, then per sentence group compute "
            f"whether all K translations collapsed to the same Rosetta canonical "
            f"address. Report agreement rates at K in "
            f"{sorted({*self._K_REPORT, self.k_max, self.primary_k})}; the "
            f"pre-registered threshold sits at K={self.primary_k} "
            f"(>= {self.agreement_threshold:.0%})."
        )

    def select_records(self, corpus: Corpus) -> Iterator[CorpusRecord]:
        for group_record in corpus.records():  # aligned mode by default
            translations = group_record.metadata.get("translations") or {}
            if not translations:
                continue
            langs = sorted(translations.keys())
            if len(langs) < self.k_max:
                # not enough parallel translations for this sentence — skip the
                # whole group so the "agreement at K_max" computation has a
                # solid denominator
                continue
            # deterministic per-group language sampling — sha256 seed so the
            # choice is reproducible across machines (Python's hash() is not)
            seed_bytes = hashlib.sha256(
                f"{self.seed}:{group_record.id}".encode("utf-8")
            ).digest()[:8]
            rng = random.Random(int.from_bytes(seed_bytes, "big"))
            chosen = rng.sample(langs, self.k_max)
            for slot, lang in enumerate(chosen):
                text = translations.get(lang, "")
                if not text:
                    continue
                yield CorpusRecord(
                    id=f"{group_record.id}:{lang}",
                    text=text,
                    metadata={
                        "sentence_group_id": group_record.id,
                        "language": lang,
                        "slot_index": slot,
                        "k_max": self.k_max,
                    },
                )

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                f"On sentence-aligned parallel text, Kimera's Rosetta layer maps "
                f"the same sentence content to the same canonical address in "
                f">= {self.agreement_threshold:.0%} of sentence groups when "
                f"{self.primary_k} languages are sampled per group (the "
                f"universal-semantic-address promise)."
            ),
            operationalization=(
                f"fraction of FLORES-200 sentence groups for which Kimera's "
                f"Rosetta returns a single distinct canonical value across "
                f"{self.primary_k} randomly-sampled language translations of "
                f"the same sentence"
            ),
            threshold=Threshold(
                f"rosetta_canonical_agreement_at_k{self.primary_k}",
                ">=",
                self.agreement_threshold,
                "fraction",
            ),
            h0=(
                f"canonical agreement at K={self.primary_k} "
                f"< {self.agreement_threshold}"
            ),
            h1=(
                f"canonical agreement at K={self.primary_k} "
                f">= {self.agreement_threshold}"
            ),
        )

    # -- result extraction -------------------------------------------------

    @staticmethod
    def _canonical(result: CycleResult) -> str | None:
        """The canonical address Rosetta returned, if any.

        Shape-aware against the real ``RosettaStele.process`` return dict
        (verified by ``ophamin_rosetta_probe.py``, 2026-05-15): the dict
        carries ``canonical`` plus ``prime`` and ``input_type``. Synthetic
        substrates may use other key names; we read the obvious ones.
        """
        if not result.success:
            return None
        raw = result.raw or {}
        for key in (
            "canonical",
            "canonical_form",
            "canonical_key",
            "canonical_concept",
        ):
            value = raw.get(key)
            if value is not None:
                return str(value)
        return None

    @staticmethod
    def _prime(result: CycleResult) -> int | None:
        """The composite prime Rosetta emitted, if any.

        Shape-aware against the real ``RosettaStele.process`` return dict
        (verified by ``ophamin_rosetta_probe.py``, 2026-05-15): the top-level
        dict carries a nested ``prime`` field whose value is itself a dict
        ``{"composite", "p_thermo", "p_identity", "canonical", ...}``. The
        scalar ``composite`` is what we compare across languages; ``p_thermo``
        and ``p_identity`` are documented secondaries. Synthetic substrates
        may put the composite at top level (``raw["composite"]``).
        """
        if not result.success:
            return None
        raw = result.raw or {}
        # nested-dict case (live Kimera)
        nested = raw.get("prime")
        if isinstance(nested, dict):
            for nested_key in ("composite", "p_identity", "p_thermo"):
                value = nested.get(nested_key)
                if value is None:
                    continue
                try:
                    return int(value)
                except (TypeError, ValueError):
                    continue
        # scalar-top-level case (synthetic substrates)
        for key in ("composite", "prime", "p_thermo"):
            value = raw.get(key)
            if value is None or isinstance(value, dict):
                continue
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
        return None

    @staticmethod
    def _wilson_ci(successes: int, total: int) -> tuple[float | None, float | None]:
        if not total:
            return None, None
        lo, hi = proportion_confint(successes, total, alpha=0.05, method="wilson")
        return float(lo), float(hi)

    # -- score -------------------------------------------------------------

    def score(
        self, cycle_results: list[CycleResult], records: list[CorpusRecord]
    ) -> ScenarioScore:
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        adapter_errors = 0
        for result, record in zip(cycle_results, records):
            if result.halt_mode == "adapter_error":
                adapter_errors += 1
            group_id = record.metadata.get("sentence_group_id")
            if not group_id:
                continue
            groups[group_id].append(
                {
                    "slot": int(record.metadata.get("slot_index", -1)),
                    "language": str(record.metadata.get("language", "")),
                    "canonical": self._canonical(result),
                    "prime": self._prime(result),
                    "success": bool(result.success),
                }
            )

        k_values = sorted(
            {*self._K_REPORT, self.k_max, self.primary_k}
        )

        def _agreement_at_k(k: int) -> dict[str, Any]:
            n_groups = 0
            agreed_canonical = 0
            agreed_prime = 0
            for entries in groups.values():
                first_k = sorted(entries, key=lambda e: e["slot"])[:k]
                if len(first_k) < k:
                    continue
                n_groups += 1
                canonicals = [e["canonical"] for e in first_k]
                primes = [e["prime"] for e in first_k]
                if all(c is not None for c in canonicals) and len(set(canonicals)) == 1:
                    agreed_canonical += 1
                if all(p is not None for p in primes) and len(set(primes)) == 1:
                    agreed_prime += 1
            return {
                "n_groups": n_groups,
                "agreed_canonical": agreed_canonical,
                "agreed_prime": agreed_prime,
                "canonical_rate": agreed_canonical / n_groups if n_groups else 0.0,
                "prime_rate": agreed_prime / n_groups if n_groups else 0.0,
            }

        per_k = {k: _agreement_at_k(k) for k in k_values}
        primary = per_k[self.primary_k]
        ng = primary["n_groups"]
        ac = primary["agreed_canonical"]
        ap = primary["agreed_prime"]
        c_lo, c_hi = self._wilson_ci(ac, ng)
        p_lo, p_hi = self._wilson_ci(ap, ng)
        observed_value = primary["canonical_rate"]

        _lib = _statsmodels.__version__
        n = len(cycle_results)
        evidence = [
            PillarEvidence(
                pillar="O.rosetta.canonical_agreement",
                statistic_name=f"rosetta_canonical_agreement_at_k{self.primary_k}",
                statistic_value=observed_value,
                library="statsmodels",
                library_version=_lib,
                ci_low=c_lo,
                ci_high=c_hi,
                cross_check="n/a",
                detail={
                    "k": self.primary_k,
                    "k_max": self.k_max,
                    "n_groups": ng,
                    "agreed_groups": ac,
                    "k_values": k_values,
                    "per_k": per_k,
                    "adapter_errors": adapter_errors,
                    "ci_method": "wilson_95",
                    "seed": self.seed,
                },
            ),
            PillarEvidence(
                pillar="O.rosetta.prime_agreement",
                statistic_name=f"rosetta_prime_agreement_at_k{self.primary_k}",
                statistic_value=primary["prime_rate"],
                library="statsmodels",
                library_version=_lib,
                ci_low=p_lo,
                ci_high=p_hi,
                cross_check="n/a",
                detail={
                    "k": self.primary_k,
                    "n_groups": ng,
                    "agreed_groups": ap,
                    "ci_method": "wilson_95",
                },
            ),
        ]

        too_few_groups = ng < 10
        not_exercised = n > 0 and adapter_errors > n // 2
        inconclusive = too_few_groups or not_exercised

        reasoning = (
            f"Rosetta canonical agreement at K={self.primary_k}: "
            f"{ac}/{ng} groups all-agree ({observed_value:.1%}); "
            f"prime agreement at K={self.primary_k}: "
            f"{ap}/{ng} ({primary['prime_rate']:.1%}); "
            f"{n} cycles, {adapter_errors} adapter errors"
        )
        if too_few_groups:
            reasoning += "; too few complete sentence groups to decide"
        elif not_exercised:
            reasoning += "; substrate not exercised (majority adapter errors)"

        return ScenarioScore(
            observed_value=observed_value,
            evidence=evidence,
            inconclusive=inconclusive,
            reasoning=reasoning,
        )
