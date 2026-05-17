"""The substrate-under-test abstraction.

Ophamin is independent of any particular system. Whatever it tests is a
``SubstrateUnderTest`` (SUT): something that can be reset, run for one cycle on
a stimulus, and asked for its git commit and state. ``MockSubstrate`` implements
this with no dependencies (so the framework is fully runnable on its own);
``KimeraAdapter`` implements it over a subprocess boundary to Kimera-SWM.

The cycle boundary is deliberate. Per the leak-free probe shape established
empirically (a fresh interpreter per cycle removes process-level state carry),
``run_cycle`` is the unit of measurement and ``reset`` is honoured between runs.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any

from ophamin._stability import Stable
from ophamin.measuring.metrics.tiers import MetricBundle, Tier1Metrics, Tier2Metrics, Tier3Metrics


@Stable(since="0.5.0", notes="The substrate-adapter return shape; load-bearing for every adapter.")
@dataclass
class CycleResult:
    """The outcome of one substrate cycle.

    ``raw`` is whatever the substrate emitted, untouched. ``success`` and
    ``halt_mode`` are the two cross-substrate fields every adapter must fill.
    A pre-built ``metric_bundle`` may be attached by the adapter; otherwise
    ``to_metric_bundle`` does best-effort extraction from ``raw``.
    """

    cycle_index: int
    success: bool
    raw: dict[str, Any] = field(default_factory=dict)
    halt_mode: str | None = None
    stimulus_id: str | None = None
    error: str | None = None
    metric_bundle: MetricBundle | None = None

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)

    def to_metric_bundle(self) -> MetricBundle:
        """Return the attached bundle, or build one with best-effort extraction.

        The default extraction recognises a small set of conventional field
        names. Adapters that know their substrate should attach an explicit
        ``metric_bundle`` rather than relying on this.
        """
        if self.metric_bundle is not None:
            return self.metric_bundle

        t1 = Tier1Metrics()
        t2 = Tier2Metrics()
        t3 = Tier3Metrics()

        for k, v in self.raw.items():
            if not isinstance(v, (int, float, bool)):
                continue
            fv = float(v)
            kl = k.lower()
            if kl.startswith(("total_", "count_", "n_")) or kl.endswith(("_count", "_total")):
                t1.counters[k] = fv
            elif "latency" in kl or kl.endswith(("_ms", "_us", "_ns", "_seconds")):
                t1.record_timer(k, fv)
            elif "drift" in kl:
                t2.drift_score = fv
            elif kl in ("phi", "prime_deformation_delta"):
                t3.prime_deformation_delta = fv
            elif "jaccard" in kl:
                t3.jaccard_overlap = fv
            else:
                t1.gauges[k] = fv

        return MetricBundle(
            cycle_index=self.cycle_index,
            tier1=t1,
            tier2=t2,
            tier3=t3,
            stimulus_id=self.stimulus_id,
        )


@Stable(since="0.5.0", notes="The plug-in protocol every substrate adapter must implement.")
class SubstrateUnderTest(abc.ABC):
    """Abstract system under test. Implement this to plug a system into Ophamin."""

    #: short stable identifier, e.g. "mock" or "kimera-swm"
    name: str = "substrate"

    @abc.abstractmethod
    def git_commit(self) -> str:
        """Return the substrate's source revision.

        This is the ``data_git_commit_id`` end of the provenance bridge: every
        recorded run is tethered to the exact substrate revision that produced it.
        Return ``""`` only if the substrate genuinely has no version anchor.
        """

    @abc.abstractmethod
    def reset(self) -> None:
        """Return the substrate to a clean initial state between runs."""

    @abc.abstractmethod
    def run_cycle(self, stimulus: Any, params: dict[str, Any] | None = None) -> CycleResult:
        """Exercise the substrate for exactly one cycle on ``stimulus``.

        ``params`` carries the swept configuration for this run. Implementations
        must not silently degrade: if the cycle cannot run, return a
        ``CycleResult`` with ``success=False`` and a populated ``error``, or
        raise — never fabricate a plausible-looking result.
        """

    def run_batch(
        self, stimuli: list[Any], params: dict[str, Any] | None = None
    ) -> list[CycleResult]:
        """Exercise the substrate over a batch of stimuli.

        The default implementation simply loops ``run_cycle`` — correct, but one
        boundary crossing per cycle. Adapters that can run a whole batch inside a
        single process (the leak-tolerant *density* path) should override this;
        ``cycle_index`` is renumbered sequentially across the batch.
        """
        results: list[CycleResult] = []
        for i, stimulus in enumerate(stimuli):
            result = self.run_cycle(stimulus, params)
            result.cycle_index = i
            results.append(result)
        return results

    def capture_state(self) -> dict[str, Any]:
        """Return a serialisable snapshot of substrate state (for provenance).

        Default is empty; substrates with inspectable state should override.
        """
        return {}

    def metadata(self) -> dict[str, Any]:
        """Static descriptive metadata about this substrate."""
        return {"name": self.name, "git_commit": self.git_commit()}
