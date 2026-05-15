"""Wheel 5 — Instrumenting.

The middle wheel of Ophamin's *inner* triad: dynamic profiling and runtime
telemetry against Kimera-SWM. Where ``seeing/`` reads what the substrate
*emits* (field schemas, corpus records, discovery), ``instrumenting/`` reads
what the substrate *costs* — wall-time, CPU, memory, page-faults, GPU,
threads — per cycle and per batch.

Two phases (per the user's "external first, then internal" decision):

  Phase 1 — external profiling, no Kimera changes
    ResourceWatcher           psutil-based pre/post snapshots around a
                              substrate batch; per-cycle wall-time comes
                              from the adapter's own cycle_seconds; CPU /
                              RSS / page-faults / thread-count / GPU are
                              attributed to the batch and averaged per cycle
    InstrumentedSubstrate     decorator that wraps any ``SubstrateProbe`` and
                              captures resource profiles on every run_batch
    BatchResourceProfile      frozen dataclass with per-batch totals + per-
                              cycle distributions (median, mean, p10/p90)
                              suitable as PillarEvidence in a proof record
    CycleResourceProfile      one-cycle snapshot (wall_time + attributed
                              CPU/RSS)

  Phase 2 — optional richer telemetry (separate module)
    py-spy / memray flamegraphs against the Kimera subprocess
    OpenTelemetry exporters for downstream Jaeger / Tempo / Honeycomb
    nvidia-smi / Metal GPU samplers

The Kimera-side internal-hook proposal lives in
``experiments/observatory/proposals/`` on the Kimera side (Tier-2, owner-
gated). Phase 2's external profilers + OpenTelemetry exporters work today
without it.
"""

from __future__ import annotations

from ophamin.instrumenting.resource_metrics import (
    BatchResourceProfile,
    CycleResourceProfile,
    ResourceWatcher,
    ResourceSample,
)
from ophamin.instrumenting.wrapper import InstrumentedSubstrate

__all__ = [
    "BatchResourceProfile",
    "CycleResourceProfile",
    "InstrumentedSubstrate",
    "ResourceSample",
    "ResourceWatcher",
]
