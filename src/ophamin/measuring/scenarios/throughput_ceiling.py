"""The Throughput Ceiling scenario — engineering-tier scenario variant.

The user's expanded Ophamin vision named three experimentation tiers:
philosophical, engineering, and scientific. The four shipped scenarios
(Immune Siege, Rosetta Scaling, Organizational Dissonance, Logic-Topology
Siege) are all *scientific* — they pre-register a falsifiable claim about
the substrate's behaviour. This scenario is the first *engineering* variant:
the pre-registered claim is about Kimera's per-cycle resource cost, not its
cognitive output.

Pre-registered claim (default):

  P(cycle_wall_time_s | x) <= ceiling at the 95th percentile

where ``cycle_wall_time_s`` is the per-cycle wall-time captured by Kimera's
adapter (exact per-cycle, not attributed), aggregated across a balanced
text corpus. A REFUTED verdict (p95 above the ceiling) surfaces a real
throughput regression; a VALIDATED verdict pins the substrate's engineering
operating point.

Composes ``ophamin.instrumenting.InstrumentedSubstrate`` over whichever base
substrate the harness passes — if the user already wraps the adapter in an
``InstrumentedSubstrate``, the scenario reuses it; otherwise wraps
transparently. ``InstrumentedSubstrate.last_profile()`` is the source of
secondary descriptive evidence (batch CPU total, RSS peak, threads,
process tree).
"""

from __future__ import annotations

from pathlib import Path
from statistics import mean, median
from typing import Iterator

import statsmodels as _statsmodels

from ophamin.instrumenting import InstrumentedSubstrate
from ophamin.measuring.proof import Claim, PillarEvidence, Threshold
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, Scenario, ScenarioScore
from ophamin.seeing.corpus.base import Corpus, CorpusRecord
from ophamin.seeing.substrate.base import CycleResult, SubstrateUnderTest


class ThroughputCeilingScenario(Scenario):
    """Engineering-tier scenario: p95 per-cycle wall-time ceiling."""

    name = "throughput-ceiling"
    corpus_name = "cyber"               # any text corpus works; cyber has labelled records
    target = "entity"

    #: cap on stimulus body length so a degenerate long-record doesn't
    #: distort the cycle distribution
    _MAX_BODY_LENGTH = 2000
    #: minimum body length to skip empty / trivial records
    _MIN_BODY_LENGTH = 50

    def __init__(
        self,
        n_cycles: int = 200,
        p95_wall_time_ceiling_s: float = 5.0,
    ) -> None:
        if p95_wall_time_ceiling_s <= 0:
            raise ValueError(
                f"p95_wall_time_ceiling_s must be > 0, got {p95_wall_time_ceiling_s}"
            )
        self.n_cycles = int(n_cycles)
        self.p95_wall_time_ceiling_s = float(p95_wall_time_ceiling_s)
        # populated by run(); read in score()
        self._instrumented: InstrumentedSubstrate | None = None

    # -- harness contract --------------------------------------------------

    def analysis_plan(self) -> str:
        return (
            f"Stream up to {self.n_cycles} balanced text records through "
            f"Kimera's entity target wrapped in InstrumentedSubstrate, then "
            f"compute the per-cycle wall-time distribution from the adapter's "
            f"own ``cycle_seconds`` field. Pre-registered threshold: 95th-"
            f"percentile cycle wall-time <= {self.p95_wall_time_ceiling_s:.2f}s. "
            f"Secondary descriptive evidence reports the median / p50 / p99 "
            f"wall-time, batch CPU total (from the periodic subprocess "
            f"sampler), RSS peak, and process-tree maximums."
        )

    def select_records(self, corpus: Corpus) -> Iterator[CorpusRecord]:
        """Use a balanced cross-section of the corpus. For corpora with the
        ``records_from`` interface (cyber, financial), prefer the labelled
        prompt-injection sub-source's interleave behaviour; for the rest,
        take the plain ``records()`` stream."""
        records_from = getattr(corpus, "records_from", None)
        if records_from is not None:
            try:
                stream = records_from("prompt_injection")
            except (ValueError, TypeError):
                stream = corpus.records()
        else:
            stream = corpus.records()
        for record in stream:
            body = (record.text or "").strip()
            if len(body) < self._MIN_BODY_LENGTH:
                continue
            if len(body) > self._MAX_BODY_LENGTH:
                body = body[: self._MAX_BODY_LENGTH]
            yield CorpusRecord(
                id=record.id,
                text=body,
                metadata={
                    **(record.metadata or {}),
                    "body_length": len(body),
                },
            )

    def build_claim(self) -> Claim:
        return Claim(
            statement=(
                f"Under sustained load on a balanced text corpus, Kimera's "
                f"entity target completes each cycle in under "
                f"{self.p95_wall_time_ceiling_s:.2f} seconds at the 95th "
                f"percentile (the architectural throughput ceiling)."
            ),
            operationalization=(
                "95th-percentile of per-cycle wall-time (raw['cycle_seconds']) "
                "across the streamed batch; cycles that failed to record a "
                "cycle_seconds are excluded from the denominator"
            ),
            threshold=Threshold(
                "p95_cycle_wall_time_s",
                "<=",
                self.p95_wall_time_ceiling_s,
                "seconds",
            ),
            h0=f"p95 wall-time > {self.p95_wall_time_ceiling_s:.2f}s",
            h1=f"p95 wall-time <= {self.p95_wall_time_ceiling_s:.2f}s",
        )

    # -- substrate wrapping ------------------------------------------------

    def run(
        self,
        substrate: SubstrateUnderTest,
        *,
        data_root: Path | None = None,
        sign_key: bytes = DEFAULT_SIGN_KEY,
    ):
        """Override Scenario.run to wrap the substrate in InstrumentedSubstrate.

        The wrapping preserves the substrate's interface; the resulting
        InstrumentedSubstrate is what the base run() actually calls. The
        wrapper's ``last_profile()`` becomes the source of secondary
        descriptive evidence in ``score``.

        If the caller already provided an InstrumentedSubstrate, we reuse it
        — this lets external code attach extra observers (e.g. a custom
        ResourceWatcher PID) before passing it in.
        """
        if isinstance(substrate, InstrumentedSubstrate):
            self._instrumented = substrate
        else:
            self._instrumented = InstrumentedSubstrate(substrate)
        return super().run(self._instrumented, data_root=data_root, sign_key=sign_key)

    # -- scoring -----------------------------------------------------------

    @staticmethod
    def _percentile(values: list[float], p: float) -> float:
        """Linear-interpolated percentile (matches numpy's default)."""
        if not values:
            return 0.0
        s = sorted(values)
        if len(s) == 1:
            return s[0]
        # rank position
        rank = (p / 100.0) * (len(s) - 1)
        lo = int(rank)
        hi = min(lo + 1, len(s) - 1)
        frac = rank - lo
        return s[lo] * (1.0 - frac) + s[hi] * frac

    @staticmethod
    def _cycle_wall_time(result: CycleResult) -> float | None:
        """Per-cycle wall-time from the adapter's ``cycle_seconds`` field."""
        if not result.success:
            return None
        raw = result.raw or {}
        value = raw.get("cycle_seconds")
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _is_adapter_error(result: CycleResult) -> bool:
        return (result.halt_mode or "").strip().lower() == "adapter_error"

    def score(
        self, cycle_results: list[CycleResult], records: list[CorpusRecord]
    ) -> ScenarioScore:
        n = len(cycle_results)
        adapter_errors = sum(1 for r in cycle_results if self._is_adapter_error(r))
        wall_times: list[float] = []
        for result in cycle_results:
            wall = self._cycle_wall_time(result)
            if wall is not None and wall >= 0:
                wall_times.append(wall)

        # primary metric: p95 cycle wall-time
        p95 = self._percentile(wall_times, 95.0)
        p50 = self._percentile(wall_times, 50.0)
        p99 = self._percentile(wall_times, 99.0)
        mean_wall = mean(wall_times) if wall_times else 0.0
        min_wall = min(wall_times) if wall_times else 0.0
        max_wall = max(wall_times) if wall_times else 0.0

        # batch-level resource attribution from the instrumenting wheel
        profile = (
            self._instrumented.last_profile()
            if self._instrumented is not None else None
        )

        _lib = _statsmodels.__version__
        evidence: list[PillarEvidence] = [
            PillarEvidence(
                pillar="O.engineering.p95_wall_time",
                statistic_name="p95_cycle_wall_time_s",
                statistic_value=p95,
                library="python-stdlib",
                library_version="3.14",
                ci_low=None,         # percentiles don't carry a Wilson CI; could
                ci_high=None,        # bootstrap for one but stdlib doesn't ship it
                cross_check="n/a",
                detail={
                    "n_cycles_measured": len(wall_times),
                    "n_cycles_total": n,
                    "adapter_errors": adapter_errors,
                    "ceiling_s": self.p95_wall_time_ceiling_s,
                },
            ),
            PillarEvidence(
                pillar="O.engineering.wall_time_distribution",
                statistic_name="cycle_wall_time_distribution",
                statistic_value=p50,  # median used as the headline value
                library="python-stdlib",
                library_version="3.14",
                cross_check="n/a",
                detail={
                    "n": len(wall_times),
                    "min": min_wall, "max": max_wall,
                    "median": p50, "mean": mean_wall,
                    "p95": p95, "p99": p99,
                },
            ),
        ]

        if profile is not None:
            # the InstrumentedSubstrate's BatchResourceProfile carries the
            # subprocess-inclusive CPU / RSS / threads
            evidence.append(PillarEvidence(
                pillar="O.engineering.batch_cpu",
                statistic_name="batch_cpu_total_s",
                statistic_value=(
                    profile.batch_cpu_time_user_s + profile.batch_cpu_time_system_s
                ),
                library="psutil",
                library_version="7.x",
                cross_check="n/a",
                detail={
                    "user_s": profile.batch_cpu_time_user_s,
                    "system_s": profile.batch_cpu_time_system_s,
                    "cpu_source": profile.cpu_source,
                    "sampler_polls": profile.sampler_polls,
                },
            ))
            evidence.append(PillarEvidence(
                pillar="O.engineering.rss_peak",
                statistic_name="rss_peak_bytes",
                statistic_value=float(profile.rss_bytes_peak),
                library="psutil",
                library_version="7.x",
                cross_check="n/a",
                detail={
                    "rss_before_bytes": profile.rss_bytes_before,
                    "rss_after_bytes": profile.rss_bytes_after,
                    "threads_max": profile.num_threads_max,
                    "process_count_max": profile.process_count_max,
                },
            ))

        # inconclusive when too few cycles were measured or the substrate didn't run
        too_few_measured = len(wall_times) < 10
        not_exercised = n > 0 and adapter_errors > n // 2
        inconclusive = too_few_measured or not_exercised

        reasoning_parts = [
            f"measured per-cycle wall-time on {len(wall_times)}/{n} cycles "
            f"({adapter_errors} adapter errors)",
            f"distribution: median {p50:.2f}s, p95 {p95:.2f}s, p99 {p99:.2f}s "
            f"(range {min_wall:.2f}-{max_wall:.2f}s)",
        ]
        if profile is not None:
            total_cpu = profile.batch_cpu_time_user_s + profile.batch_cpu_time_system_s
            reasoning_parts.append(
                f"batch totals: wall {profile.batch_wall_time_s:.2f}s, "
                f"cpu {total_cpu:.2f}s ({profile.cpu_source}), "
                f"rss_peak {profile.rss_bytes_peak / 1e6:.1f}MB, "
                f"max threads {profile.num_threads_max}, "
                f"max procs {profile.process_count_max}"
            )
        if too_few_measured:
            reasoning_parts.append("too few cycles measured to decide")
        elif not_exercised:
            reasoning_parts.append("substrate not exercised (majority adapter errors)")

        return ScenarioScore(
            observed_value=p95,
            evidence=evidence,
            inconclusive=inconclusive,
            reasoning="; ".join(reasoning_parts),
        )
