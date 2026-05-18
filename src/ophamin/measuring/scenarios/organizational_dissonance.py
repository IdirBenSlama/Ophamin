"""The Organizational Dissonance scenario.

Streams real organizational email (Enron CMU release, ~500k executive emails)
through Kimera's entity target (Takwin) and measures whether the dissonance
machinery fires reliably on routine non-engineered organizational text.

Probe finding (2026-05-15, n=8 hand-picked stimuli): on GWF-cleared inputs the
dissonance layer fires 10-21 dissonance events with productive_dissonance_score
0.30-0.79; on GWF-blocked inputs the dissonance fields collapse to zero
(dissonance runs downstream of GWF; blocked → short-circuit). The
pre-registered claim mirrors that architecture: on cleared cycles, the
dissonance machinery should be reliably *active*.

Pre-registered claim — "active dissonance ceiling":

  P(dissonance_events_count >= 1 | gwf_verdict cleared) >= 0.90

A REFUTED verdict (the dissonance layer is silent on routine organizational
content more often than 10% of the time) would surface a wiring or
calibration gap. A VALIDATED verdict pins the layer's baseline activity on
real-world signal as a useful operating point.

Secondary evidence (descriptive, not pre-registered): the distribution of
dissonance_events_count and productive_dissonance_score across the corpus,
the GWF block rate on Enron, and the manipulation_detector rate. These
characterize the substrate's behavior on a real organizational corpus
*without* taking external labels as ground truth.
"""

from __future__ import annotations

from statistics import mean, median
from typing import Iterator, Sequence

import statsmodels as _statsmodels
from statsmodels.stats.proportion import proportion_confint

from ophamin.seeing.corpus import Corpus, CorpusRecord
from ophamin.measuring.proof import Claim, PillarEvidence, Threshold
from ophamin.measuring.scenarios.base import Scenario, ScenarioScore, Tier
from ophamin.seeing.substrate.base import CycleResult


class OrganizationalDissonanceScenario(Scenario):
    """Dissonance-layer firing rate on routine organizational email."""

    name = "organizational-dissonance"
    tier = Tier.SCIENTIFIC
    family = "dissonance"
    runner_path = "examples/run_organizational_dissonance.py"
    goal = (
        "Measure whether Kimera's dissonance machinery fires reliably "
        "on routine non-engineered organizational text."
    )
    explanation = (
        "The dissonance layer downstream of GWF should be reliably "
        "ACTIVE on real-world organizational content — silence on "
        "routine input would indicate a wiring or calibration gap. "
        "This scenario streams ~500k Enron executive emails through "
        "Takwin and measures the fraction of GWF-cleared cycles in "
        "which dissonance_events_count >= 1. The threshold (default "
        "90%) pins the layer's expected baseline activity."
    )
    method = "wilson_ci_proportion"
    falsification_consequence = (
        "The dissonance layer is silent on routine organizational "
        "content more than 10% of the time — surfaces a wiring or "
        "calibration gap downstream of GWF."
    )
    corpus_name = "enron"
    target = "entity"

    # the smallest body length we consider "real" content (under this is
    # mostly auto-generated bounce / autoreply / signature-only — not the
    # organizational signal we're after)
    _MIN_BODY_LENGTH = 100
    # cap a single email body so a degenerate forwarded chain doesn't dominate
    # the substrate's per-cycle budget (Kimera's encoder window is finite)
    _MAX_BODY_LENGTH = 4000

    def __init__(
        self,
        n_cycles: int = 1000,
        active_floor: float = 0.90,
    ) -> None:
        if not 0.0 <= active_floor <= 1.0:
            raise ValueError(f"active_floor must be in [0, 1], got {active_floor}")
        self.n_cycles = int(n_cycles)
        self.active_floor = float(active_floor)

    # -- harness contract --------------------------------------------------

    def analysis_plan(self) -> str:
        return (
            f"Stream up to {self.n_cycles} real Enron emails (body length in "
            f"[{self._MIN_BODY_LENGTH}, {self._MAX_BODY_LENGTH}] chars) through "
            f"Kimera's entity target (Takwin), then measure the fraction of "
            f"GWF-cleared cycles for which the dissonance machinery fired "
            f"(dissonance_events_count >= 1). Pre-registered threshold: "
            f">= {self.active_floor:.0%}. Secondary descriptive evidence reports "
            f"the distribution of dissonance_events_count and "
            f"productive_dissonance_score, the GWF block rate on Enron, and "
            f"the manipulation_detector rate — none post-hoc-claimable."
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
                metadata={
                    **record.metadata,
                    "body_length": len(body),
                    "body_truncated": len((record.text or "").strip()) > self._MAX_BODY_LENGTH,
                },
            )

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                f"On routine organizational email that clears Kimera's GWF, the "
                f"dissonance machinery fires (dissonance_events_count >= 1) in "
                f">= {self.active_floor:.0%} of cycles (the architectural "
                f"active-dissonance floor)."
            ),
            operationalization=(
                "fraction of GWF-cleared Enron-email cycles for which "
                "raw['dissonance_events'] is a non-empty list"
            ),
            threshold=Threshold(
                "dissonance_active_rate_on_cleared",
                ">=",
                self.active_floor,
                "fraction",
            ),
            h0=(
                f"P(dissonance fires | gwf cleared) < {self.active_floor}"
            ),
            h1=(
                f"P(dissonance fires | gwf cleared) >= {self.active_floor}"
            ),
        )

    # -- result extraction -------------------------------------------------

    @staticmethod
    def _gwf_cleared(result: CycleResult) -> bool:
        """Did the GWF clear this input? Shape-aware on the entity raw dict.

        Mirrors ``ImmuneSiegeScenario._is_blocked`` (entity branch): a cleared
        verdict is ``gwf_verdict == "cleared"`` and not a lockdown.
        """
        if not result.success:
            return False
        raw = result.raw or {}
        if raw.get("gwf_lockdown") is True:
            return False
        verdict = str(raw.get("gwf_verdict", "")).strip().lower()
        if verdict.startswith("blocked") or "lockdown" in verdict:
            return False
        # "cleared" or empty (synthetic substrates) -> cleared-by-default
        return True

    @staticmethod
    def _dissonance_count(result: CycleResult) -> int:
        """Number of dissonance events raised this cycle.

        Reads ``raw["dissonance_events"]`` — the canonical list field per
        Family L's 17-field dissonance-layer inventory. The synthetic
        substrate fallback also reads ``dissonance_event_count`` /
        ``zetetic_contradictions`` for symmetry.
        """
        if not result.success:
            return 0
        raw = result.raw or {}
        events = raw.get("dissonance_events")
        if isinstance(events, list):
            return len(events)
        count = raw.get("dissonance_event_count")
        if isinstance(count, int):
            return count
        zet = raw.get("zetetic_contradictions")
        if isinstance(zet, list):
            return len(zet)
        return 0

    @staticmethod
    def _productive_dissonance_score(result: CycleResult) -> float:
        if not result.success:
            return 0.0
        raw = result.raw or {}
        value = raw.get("productive_dissonance_score")
        try:
            return float(value) if value is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _manipulation_detected(result: CycleResult) -> bool:
        if not result.success:
            return False
        raw = result.raw or {}
        return raw.get("manipulation_detected") is True

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
        n = len(cycle_results)
        adapter_errors = 0
        cleared_total = 0
        cleared_active = 0
        gwf_blocks = 0
        manipulation_detections = 0
        diss_counts: list[int] = []  # all GWF-cleared cycles
        pds_scores: list[float] = []  # all GWF-cleared cycles
        for result in cycle_results:
            if result.halt_mode == "adapter_error":
                adapter_errors += 1
                continue
            cleared = self._gwf_cleared(result)
            if cleared:
                cleared_total += 1
                d = self._dissonance_count(result)
                pds = self._productive_dissonance_score(result)
                diss_counts.append(d)
                pds_scores.append(pds)
                if d >= 1:
                    cleared_active += 1
            else:
                gwf_blocks += 1
            if self._manipulation_detected(result):
                manipulation_detections += 1

        active_rate = cleared_active / cleared_total if cleared_total else 0.0
        gwf_block_rate = gwf_blocks / max(1, n - adapter_errors)
        manipulation_rate = manipulation_detections / max(1, n - adapter_errors)
        active_lo, active_hi = self._wilson_ci(cleared_active, cleared_total)

        diss_stats = self._distribution_stats(diss_counts)
        pds_stats = self._distribution_stats(pds_scores)

        _lib = _statsmodels.__version__
        evidence = [
            PillarEvidence(
                pillar="O.dissonance.active_on_cleared",
                statistic_name="dissonance_active_rate_on_cleared",
                statistic_value=active_rate,
                library="statsmodels",
                library_version=_lib,
                ci_low=active_lo,
                ci_high=active_hi,
                cross_check="n/a",
                detail={
                    "cleared_active": cleared_active,
                    "cleared_total": cleared_total,
                    "ci_method": "wilson_95",
                    "n_cycles": n,
                    "adapter_errors": adapter_errors,
                },
            ),
            PillarEvidence(
                pillar="O.dissonance.intensity_distribution",
                statistic_name="dissonance_events_count_median",
                statistic_value=diss_stats["median"],
                library="python-stdlib",
                library_version="3.14",
                cross_check="n/a",
                detail={
                    "distribution": diss_stats,
                    "field": "dissonance_events_count",
                    "denominator": "GWF-cleared cycles",
                },
            ),
            PillarEvidence(
                pillar="O.dissonance.productive_score",
                statistic_name="productive_dissonance_score_median",
                statistic_value=pds_stats["median"],
                library="python-stdlib",
                library_version="3.14",
                cross_check="n/a",
                detail={
                    "distribution": pds_stats,
                    "field": "productive_dissonance_score",
                    "denominator": "GWF-cleared cycles",
                },
            ),
            PillarEvidence(
                pillar="O.organizational.gwf_block_rate",
                statistic_name="gwf_block_rate_on_enron",
                statistic_value=gwf_block_rate,
                library="ophamin",
                library_version="0.1.0",
                cross_check="n/a",
                detail={
                    "gwf_blocks": gwf_blocks,
                    "denominator": max(1, n - adapter_errors),
                    "note": (
                        "GWF block rate on routine Enron email is a "
                        "descriptive ceiling — high values would indicate "
                        "GWF over-eagerness on neutral organizational signal"
                    ),
                },
            ),
            PillarEvidence(
                pillar="O.organizational.manipulation_rate",
                statistic_name="manipulation_detected_rate_on_enron",
                statistic_value=manipulation_rate,
                library="ophamin",
                library_version="0.1.0",
                cross_check="n/a",
                detail={
                    "manipulation_detections": manipulation_detections,
                    "denominator": max(1, n - adapter_errors),
                },
            ),
        ]

        # the run is inconclusive if too few GWF-cleared cycles were seen
        # (we need a solid cleared denominator for the Wilson CI), or if the
        # substrate was not actually exercised
        too_few_cleared = cleared_total < 10
        not_exercised = n > 0 and adapter_errors > n // 2
        inconclusive = too_few_cleared or not_exercised

        reasoning = (
            f"dissonance fired in {cleared_active}/{cleared_total} "
            f"GWF-cleared cycles ({active_rate:.1%}); "
            f"GWF blocked {gwf_blocks}/{n - adapter_errors} "
            f"({gwf_block_rate:.1%}); "
            f"manipulation_detected in {manipulation_detections}/{n - adapter_errors} "
            f"({manipulation_rate:.1%}); "
            f"dissonance_events median={diss_stats['median']:.0f} "
            f"(range {diss_stats['min']:.0f}-{diss_stats['max']:.0f}); "
            f"{n} cycles, {adapter_errors} adapter errors"
        )
        if too_few_cleared:
            reasoning += "; too few GWF-cleared cycles to decide"
        elif not_exercised:
            reasoning += "; substrate not exercised (majority adapter errors)"

        return ScenarioScore(
            observed_value=active_rate,
            evidence=evidence,
            inconclusive=inconclusive,
            reasoning=reasoning,
        )

    @staticmethod
    def _distribution_stats(values: Sequence[float | int]) -> dict[str, float | int]:
        """Cheap descriptive stats — never report distribution claims as
        falsifiable; these are *descriptive secondary evidence* per the
        Empirical Proof Record discipline."""
        if not values:
            return {
                "n": 0,
                "min": 0.0,
                "max": 0.0,
                "median": 0.0,
                "mean": 0.0,
                "p10": 0.0,
                "p90": 0.0,
            }
        sorted_v = sorted(float(v) for v in values)
        n = len(sorted_v)
        return {
            "n": n,
            "min": sorted_v[0],
            "max": sorted_v[-1],
            "median": float(median(sorted_v)),
            "mean": float(mean(sorted_v)),
            "p10": sorted_v[max(0, int(n * 0.10) - 1)],
            "p90": sorted_v[min(n - 1, int(n * 0.90))],
        }
