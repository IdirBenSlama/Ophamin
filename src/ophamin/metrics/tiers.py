"""Hierarchical metric model — the three tiers from the Ophamin blueprint.

When a substrate is exercised across many cycles, raw variable dumps are not
enough. Metrics are separated into functional tiers so operational health is
never conflated with cognitive evaluation:

    Tier 1  high-frequency system telemetry  (counters / gauges / timers)
    Tier 2  causal & statistical observability (drives the stopping rules)
    Tier 3  domain-specific cognitive output (the substrate's actual product)

A ``MetricBundle`` is one cycle's worth of all three tiers. Adapters populate
the bundle; pillars consume it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Tier1Metrics:
    """High-frequency system telemetry — health and latency."""

    counters: dict[str, float] = field(default_factory=dict)
    """Cumulative monotonic events (e.g. total_cycles, threats_blocked)."""

    gauges: dict[str, float] = field(default_factory=dict)
    """Point-in-time measurements (e.g. energy_reserve, memory_utilization)."""

    timers: dict[str, list[float]] = field(default_factory=dict)
    """Distributions of execution speeds — kept as raw samples for histograms."""

    def record_timer(self, name: str, value: float) -> None:
        self.timers.setdefault(name, []).append(float(value))

    def to_dict(self) -> dict[str, Any]:
        return {
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "timers": {k: list(v) for k, v in self.timers.items()},
        }


@dataclass
class Tier2Metrics:
    """Causal and statistical observability — governs experiment validity.

    These values trigger automated stopping rules and diagnostic alerts.
    """

    srm_pvalue: float | None = None
    """Continuous chi-squared p-value evaluating routing integrity."""

    sprt_llr: float | None = None
    """Cumulative log-likelihood ratio of the sequential test."""

    msprt_pvalue: float | None = None
    """Always-valid (anytime) p-value from the mixture SPRT."""

    drift_score: float | None = None
    """Divergence of the input stream against the baseline distribution."""

    extra: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "srm_pvalue": self.srm_pvalue,
            "sprt_llr": self.sprt_llr,
            "msprt_pvalue": self.msprt_pvalue,
            "drift_score": self.drift_score,
        }
        d.update(self.extra)
        return d


@dataclass
class Tier3Metrics:
    """Domain-specific cognitive metrics — the substrate's structural output.

    The named fields below are the examples called out in the blueprint for a
    Kimera-style substrate. Any substrate may instead use ``extra`` freely; the
    framework treats Tier-3 as opaque and substrate-defined.
    """

    prime_deformation_delta: float | None = None
    """Percentage shift in the mathematical routing of concepts."""

    zetetic_dissonance_gradient: float | None = None
    """Measurable slope of the Bayesian posterior tempering."""

    jaccard_overlap: float | None = None
    """Cross-lingual / cross-modal concept-mapping overlap."""

    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "prime_deformation_delta": self.prime_deformation_delta,
            "zetetic_dissonance_gradient": self.zetetic_dissonance_gradient,
            "jaccard_overlap": self.jaccard_overlap,
        }
        d.update(self.extra)
        return d


@dataclass
class MetricBundle:
    """One cycle's measurement across all three tiers."""

    cycle_index: int
    tier1: Tier1Metrics = field(default_factory=Tier1Metrics)
    tier2: Tier2Metrics = field(default_factory=Tier2Metrics)
    tier3: Tier3Metrics = field(default_factory=Tier3Metrics)
    stimulus_id: str | None = None
    wall_time: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_index": self.cycle_index,
            "stimulus_id": self.stimulus_id,
            "wall_time": self.wall_time,
            "tier1": self.tier1.to_dict(),
            "tier2": self.tier2.to_dict(),
            "tier3": self.tier3.to_dict(),
        }

    def flat(self) -> dict[str, Any]:
        """Flatten to a single namespaced dict — convenient for tabular analysis."""
        out: dict[str, Any] = {
            "cycle_index": self.cycle_index,
            "stimulus_id": self.stimulus_id,
        }
        for k, v in self.tier1.counters.items():
            out[f"t1.counter.{k}"] = v
        for k, v in self.tier1.gauges.items():
            out[f"t1.gauge.{k}"] = v
        for k, v in self.tier1.timers.items():
            # timers flatten to their mean; raw samples stay in tier1.timers
            out[f"t1.timer.{k}.mean"] = sum(v) / len(v) if v else None
        for k, v in self.tier2.to_dict().items():
            out[f"t2.{k}"] = v
        for k, v in self.tier3.to_dict().items():
            out[f"t3.{k}"] = v
        return out
