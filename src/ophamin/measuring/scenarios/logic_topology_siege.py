"""The Logic-Topology Siege scenario.

Streams real technical-domain text — Linux kernel commit messages (~1.4M
commits, torvalds/linux blobless bare clone) — through Kimera's entity target
(Takwin) and measures whether the substrate sustains walker traversal on
technical content (the topology layer's "engaged thinking" mode) rather than
collapsing to amplitude_death (silent walker collapse).

Probe finding (2026-05-15, n=5 hand-picked kernel-style stimuli): all 5
GWF-cleared, all 5 halt_mode=exhausted, dissonance fires 10-27 events each.
Contrast with Enron probe (2026-05-15, n=8): 6/6 GWF-cleared cycles split
between amplitude_death and exhausted (4 amplitude_death + 2 exhausted).
Technical content sustains the walker more reliably than narrative content.

Pre-registered claim — "sustained-traversal floor":

  P(halt_mode == "exhausted" | gwf_verdict cleared) >= 0.60

A REFUTED verdict (the walker collapses too readily on technical content)
would surface a calibration gap in the walker / step-budget / coherence
machinery. A VALIDATED verdict pins the substrate's engagement profile on
technical-reasoning content as a useful operating point.

Secondary evidence (descriptive, not pre-registered): halt_mode distribution
across all halt modes, dissonance-event distribution, GWF block rate on
kernel commits, Φ-value distribution. These characterize the substrate's
behavior on a real technical corpus.
"""

from __future__ import annotations

from collections import Counter
from statistics import mean, median
from typing import Iterator

import statsmodels as _statsmodels
from statsmodels.stats.proportion import proportion_confint

from ophamin.seeing.corpus import Corpus, CorpusRecord
from ophamin.measuring.proof import Claim, PillarEvidence, Threshold
from ophamin.measuring.scenarios.base import Scenario, ScenarioScore
from ophamin.seeing.substrate.base import CycleResult


class LogicTopologySiegeScenario(Scenario):
    """Walker sustained-traversal rate on Linux kernel commit messages."""

    name = "logic-topology-siege"
    corpus_name = "linux"
    target = "entity"

    _MIN_BODY_LENGTH = 80   # kernel commit subjects are short; 80 chars catches a real subject+body
    _MAX_BODY_LENGTH = 4000

    def __init__(
        self,
        n_cycles: int = 1000,
        sustained_floor: float = 0.60,
    ) -> None:
        if not 0.0 <= sustained_floor <= 1.0:
            raise ValueError(
                f"sustained_floor must be in [0, 1], got {sustained_floor}"
            )
        self.n_cycles = int(n_cycles)
        self.sustained_floor = float(sustained_floor)

    # -- harness contract --------------------------------------------------

    def analysis_plan(self) -> str:
        return (
            f"Stream up to {self.n_cycles} real Linux kernel commit messages "
            f"(body length in [{self._MIN_BODY_LENGTH}, {self._MAX_BODY_LENGTH}] "
            f"chars) through Kimera's entity target (Takwin), then measure the "
            f"fraction of GWF-cleared cycles whose halt_mode is 'exhausted' "
            f"(the substrate's sustained-traversal mode). Pre-registered "
            f"threshold: >= {self.sustained_floor:.0%}. Secondary descriptive "
            f"evidence reports the full halt-mode distribution, "
            f"dissonance-event distribution, GWF block rate, and Φ distribution "
            f"— none post-hoc-claimable."
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
                f"On real technical-domain text (Linux kernel commit messages) "
                f"that clears Kimera's GWF, the substrate's walker reaches "
                f"sustained traversal (halt_mode == 'exhausted') in "
                f">= {self.sustained_floor:.0%} of cycles — i.e. the topology "
                f"layer engages on technical reasoning instead of collapsing to "
                f"amplitude_death."
            ),
            operationalization=(
                "fraction of GWF-cleared Linux-kernel-commit cycles for which "
                "result.halt_mode == 'exhausted'"
            ),
            threshold=Threshold(
                "sustained_traversal_rate_on_cleared",
                ">=",
                self.sustained_floor,
                "fraction",
            ),
            h0=(
                f"P(halt='exhausted' | gwf cleared) < {self.sustained_floor}"
            ),
            h1=(
                f"P(halt='exhausted' | gwf cleared) >= {self.sustained_floor}"
            ),
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
    def _halt_mode(result: CycleResult) -> str:
        return (result.halt_mode or "").strip().lower()

    @staticmethod
    def _dissonance_count(result: CycleResult) -> int:
        if not result.success:
            return 0
        raw = result.raw or {}
        events = raw.get("dissonance_events")
        if isinstance(events, list):
            return len(events)
        count = raw.get("dissonance_event_count")
        if isinstance(count, int):
            return count
        return 0

    @staticmethod
    def _phi_value(result: CycleResult) -> float:
        if not result.success:
            return 0.0
        raw = result.raw or {}
        for key in ("phi_value", "phi", "Phi", "iit_phi"):
            value = raw.get(key)
            if value is None:
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return 0.0

    @staticmethod
    def _wilson_ci(successes: int, total: int) -> tuple[float | None, float | None]:
        if not total:
            return None, None
        lo, hi = proportion_confint(successes, total, alpha=0.05, method="wilson")
        return float(lo), float(hi)

    @staticmethod
    def _distribution_stats(values: list[float | int]) -> dict:
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

    # -- score -------------------------------------------------------------

    def score(
        self, cycle_results: list[CycleResult], records: list[CorpusRecord]
    ) -> ScenarioScore:
        n = len(cycle_results)
        adapter_errors = 0
        cleared_total = 0
        cleared_exhausted = 0
        cleared_amplitude_death = 0
        gwf_blocks = 0
        halt_mode_counts: Counter[str] = Counter()
        diss_counts: list[int] = []
        phi_values: list[float] = []
        for result in cycle_results:
            halt = self._halt_mode(result)
            if halt == "adapter_error":
                adapter_errors += 1
                continue
            cleared = self._gwf_cleared(result)
            if cleared:
                cleared_total += 1
                halt_mode_counts[halt] += 1
                if halt == "exhausted":
                    cleared_exhausted += 1
                elif halt == "amplitude_death":
                    cleared_amplitude_death += 1
                diss_counts.append(self._dissonance_count(result))
                phi_values.append(self._phi_value(result))
            else:
                gwf_blocks += 1

        sustained_rate = cleared_exhausted / cleared_total if cleared_total else 0.0
        amplitude_death_rate = (
            cleared_amplitude_death / cleared_total if cleared_total else 0.0
        )
        gwf_block_rate = gwf_blocks / max(1, n - adapter_errors)
        sust_lo, sust_hi = self._wilson_ci(cleared_exhausted, cleared_total)

        diss_stats = self._distribution_stats(diss_counts)
        phi_stats = self._distribution_stats(phi_values)

        _lib = _statsmodels.__version__
        evidence = [
            PillarEvidence(
                pillar="O.topology.sustained_traversal",
                statistic_name="sustained_traversal_rate_on_cleared",
                statistic_value=sustained_rate,
                library="statsmodels",
                library_version=_lib,
                ci_low=sust_lo,
                ci_high=sust_hi,
                cross_check="n/a",
                detail={
                    "cleared_exhausted": cleared_exhausted,
                    "cleared_total": cleared_total,
                    "ci_method": "wilson_95",
                    "n_cycles": n,
                    "adapter_errors": adapter_errors,
                },
            ),
            PillarEvidence(
                pillar="O.topology.amplitude_death_rate",
                statistic_name="amplitude_death_rate_on_cleared",
                statistic_value=amplitude_death_rate,
                library="ophamin",
                library_version="0.1.0",
                cross_check="n/a",
                detail={
                    "cleared_amplitude_death": cleared_amplitude_death,
                    "cleared_total": cleared_total,
                    "note": (
                        "Complementary to sustained-traversal: high rates "
                        "indicate the walker is collapsing rather than "
                        "engaging on technical content"
                    ),
                },
            ),
            PillarEvidence(
                pillar="O.topology.halt_mode_distribution",
                statistic_name="halt_modes_observed_count",
                statistic_value=float(len(halt_mode_counts)),
                library="ophamin",
                library_version="0.1.0",
                cross_check="n/a",
                detail={
                    "distribution": dict(halt_mode_counts),
                    "denominator": cleared_total,
                },
            ),
            PillarEvidence(
                pillar="O.topology.gwf_block_rate",
                statistic_name="gwf_block_rate_on_linux",
                statistic_value=gwf_block_rate,
                library="ophamin",
                library_version="0.1.0",
                cross_check="n/a",
                detail={
                    "gwf_blocks": gwf_blocks,
                    "denominator": max(1, n - adapter_errors),
                },
            ),
            PillarEvidence(
                pillar="O.topology.dissonance_intensity",
                statistic_name="dissonance_events_count_median",
                statistic_value=diss_stats["median"],
                library="python-stdlib",
                library_version="3.14",
                cross_check="n/a",
                detail={"distribution": diss_stats},
            ),
            PillarEvidence(
                pillar="O.topology.phi_distribution",
                statistic_name="phi_value_median",
                statistic_value=phi_stats["median"],
                library="python-stdlib",
                library_version="3.14",
                cross_check="n/a",
                detail={"distribution": phi_stats},
            ),
        ]

        too_few_cleared = cleared_total < 10
        not_exercised = n > 0 and adapter_errors > n // 2
        inconclusive = too_few_cleared or not_exercised

        reasoning = (
            f"walker reached sustained traversal in {cleared_exhausted}/"
            f"{cleared_total} GWF-cleared cycles ({sustained_rate:.1%}); "
            f"amplitude_death in {cleared_amplitude_death}/{cleared_total} "
            f"({amplitude_death_rate:.1%}); "
            f"GWF blocked {gwf_blocks}/{n - adapter_errors} ({gwf_block_rate:.1%}); "
            f"halt modes observed: {dict(halt_mode_counts)}; "
            f"dissonance median={diss_stats['median']:.0f} "
            f"(range {diss_stats['min']:.0f}-{diss_stats['max']:.0f}); "
            f"Φ median={phi_stats['median']:.3f}; "
            f"{n} cycles, {adapter_errors} adapter errors"
        )
        if too_few_cleared:
            reasoning += "; too few GWF-cleared cycles to decide"
        elif not_exercised:
            reasoning += "; substrate not exercised (majority adapter errors)"

        return ScenarioScore(
            observed_value=sustained_rate,
            evidence=evidence,
            inconclusive=inconclusive,
            reasoning=reasoning,
        )
