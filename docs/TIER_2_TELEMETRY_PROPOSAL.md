# Tier-2 proposal — Kimera-side internal telemetry hooks

**Status**: PROPOSED (Tier-2 per Kimera CLAUDE.md §"Fix policy — three-tier rule"). Owner-gated. Ophamin Phase 1 external profiling lands today without it; this proposal describes what Phase 2 would need from the Kimera substrate to close the per-cycle attribution gap completely.

**Author**: Ophamin (external empirical framework)
**Date**: 2026-05-15
**Pairs with**: Ophamin `instrumenting/` Phase 1 (external psutil + periodic subprocess sampler — already live)

---

## Motivation

Ophamin's external profiling (`InstrumentedSubstrate` + `ResourceWatcher` + `PeriodicSubprocessSampler`) successfully captures **per-batch** resource usage for the Kimera adapter's subprocess substrate. On a 5-cycle live smoke against the entity target (Kimera commit `a9145ac8`):

- batch_wall_time_s: **12.426** (per-cycle ~2.5s)
- batch_cpu_total_s: **13.819** (~111% CPU utilization)
- rss_peak: **1.925 GB** (Kimera subprocess, parent was 285 MB)
- process_count_max: 2 (parent + subprocess)
- threads_max: 67 (Kimera's real thread count)
- sampler_polls: 33

What external profiling **cannot** see:

1. **Per-cycle CPU/RSS precision**. Today CPU is attributed to cycles proportional to their wall-time. That's correct in expectation but loses cycle-to-cycle variance — a cycle that happened to do heavy SCAR consolidation looks the same as a cycle that did pure traversal.
2. **Substrate-internal events** — SCAR writes, KCCL phase transitions, Walker mode changes (M1/M2/M3/M4), GWF block decisions, dissonance event firings. These are visible in `result.raw` (Layer A discovery surfaces them) but not as **timed spans** with start / end / parent-child structure.
3. **GPU utilization** correlated with cycle phases. Today GPU samples (via nvidia-smi or pynvml) come from the OS, not from Kimera's actual GPU dispatch.

The fix is a per-cycle telemetry hook on the Kimera side: each step of the Takwin 7-step pipeline emits one OpenTelemetry span. Each named substrate event (SCAR write, Walker M-mode transition, GWF screen, dissonance event) emits a structured event on the active span.

## The proposal

A minimal substrate-side hook that requires NO changes to Kimera's core logic — just instrumentation. Two surfaces:

### Surface 1 — span emission around the 7 Takwin steps

In `kimera_swm/domain/cognitive/takwin.py`'s `Takwin.run` outer loop:

```python
def run(self, stimulus: str) -> OrchestratorResult:
    with self._telemetry.span("takwin.cycle") as cycle_span:
        cycle_span.set_attribute("cycle.index", self._cycle_index)
        cycle_span.set_attribute("stimulus.length", len(stimulus))
        # step2
        with self._telemetry.span("takwin.step2_encode"):
            step2 = self._step2_encode(stimulus)
        # step3+4
        with self._telemetry.span("takwin.step3_step4_traverse"):
            step34 = self._step3_step4_traverse(step2)
        # ...
```

The `self._telemetry` is a single `TelemetryEmitter` interface; the default implementation is a no-op (no measurable overhead in production). When Ophamin attaches, it injects an OpenTelemetry-backed implementation.

### Surface 2 — structured events on the active span

For each named substrate event:

```python
# in GWF
self._telemetry.event(
    "gwf.screen", attributes={
        "verdict": verdict,
        "intent_top_anchor": top_anchor,
        "intent_top_score": top_score,
    }
)

# in Walker
self._telemetry.event(
    "walker.mode_transition", attributes={
        "from_mode": prev,
        "to_mode": new,
        "phi_at_transition": phi,
    }
)

# in SCAR write
self._telemetry.event(
    "scar.write", attributes={
        "scar_id": scar_id,
        "kind": kind,
        "prime_chain_length": len(prime_chain),
    }
)
```

Events are no-op by default; under Ophamin attach they become OpenTelemetry events on the active span.

### The hook injection point

Ophamin's `InstrumentedSubstrate` would pass a telemetry-emitter handle to the KimeraAdapter's runner template. The runner constructs Kimera with the emitter wired in:

```python
# in KimeraAdapter's runner template, added behind a feature flag
if KIMERA_TELEMETRY_EMITTER_PATH:
    from kimera_swm.infrastructure.telemetry import OpenTelemetryEmitter
    emitter = OpenTelemetryEmitter(export_to=KIMERA_TELEMETRY_EMITTER_PATH)
else:
    emitter = NoOpEmitter()
component = construct(target, params, telemetry_emitter=emitter)
```

`KIMERA_TELEMETRY_EMITTER_PATH` is an env var Ophamin sets when running an instrumented batch; otherwise it's absent and Kimera runs with NoOpEmitter (zero overhead, zero behavioural change).

## Why this is Tier-2, not Tier-1 or Tier-3

Per CLAUDE.md Tier-2 definition: "Substrate code changes that ARE reversible and well-bounded (e.g., adding `__new__`-based singleton enforcement to a footgun class — three clean variants exist; agent drafts each, owner picks one to apply)."

This proposal:
- **Reversible**: each `self._telemetry.span(...)` and `.event(...)` block can be removed in one pass. Removing the emitter parameter from constructors is a single grep-replace.
- **Well-bounded**: ~50-100 instrumentation points across the canonical primitives. No primitive's behaviour changes; the emitter is a no-op by default.
- **No silent fallbacks**: per CLAUDE.md's no-fallback rule, the `NoOpEmitter` is *not* a fallback — it's the explicit default behaviour when Ophamin hasn't attached. Behaviour is identical to today.

It is NOT Tier-1 because it touches substrate code (Kimera's `takwin.py` and named primitives), and it is NOT Tier-3 because it doesn't change primitive semantics, naming, or framing.

## Alternatives considered

1. **Wrap KimeraAdapter externally only** — already done in Phase 1. Closes the parent/subprocess CPU gap but cannot see substrate-internal events.

2. **py-spy / memray flamegraphs** — Phase 2 will add these as optional. Useful but produces unstructured profiles, not span-trees aligned with the 7-step pipeline.

3. **Patch the Kimera runner template post-hoc** (monkey-patch from Ophamin) — possible but fragile; substrate semantics could shift under the patch.

4. **Make Ophamin's emitter a Kimera package** — wrong direction; couples Kimera to Ophamin.

## What Ophamin would build to consume these hooks

If accepted:

1. `ophamin.instrumenting.opentelemetry_collector` — receives Kimera's OTel spans via OTLP or in-memory exporter; aggregates per-cycle/per-step durations.
2. `BatchResourceProfile` gains a `per_step_timing` field (median / p10 / p90 wall-time per of the 7 Takwin steps).
3. Cross-commit drift detection adds **per-step performance drift** — if `step5_consolidate` median jumps from 0.4s to 1.2s between commits, Ophamin flags it via `ophamin drift-report`.
4. The reporting wheel renders per-step waterfall charts in HTML/PDF/Jupyter output.

## Acceptance criteria

If you (owner) approve, the implementation would land as a single Kimera-side PR with:

1. `kimera_swm/infrastructure/telemetry/__init__.py` (~80 LOC) — `TelemetryEmitter` protocol + `NoOpEmitter` + `OpenTelemetryEmitter` (optional import; module loads cleanly without opentelemetry).
2. Constructor + method signature additions (~50-100 instrumentation points) across `Takwin`, `GWFProtocol`, `Walker`, SCAR write paths, dissonance event emission.
3. Hardening tests pinning that:
   - With `NoOpEmitter`, behaviour is bit-identical to pre-instrumentation (hash of a 30-cycle batch's output unchanged).
   - With `OpenTelemetryEmitter`, every span emitted carries the expected attributes.
   - Zero overhead in NoOp mode (within 1% wall-time of pre-instrumentation baseline).

Phase 2 of Ophamin's `instrumenting/` (OTLP collector, py-spy/memray wrappers) lands AFTER this proposal is owner-accepted, so the receive side is ready when the emit side ships.

## Decision path

This document lives in Ophamin's `docs/` as a reference. The matching Kimera-side artefact (if you accept) would be migrated to `experiments/observatory/proposals/kimera_telemetry_hooks_2026_05_15.md` per CLAUDE.md's Tier-2 protocol.

Until then, Phase 1 stands. Ophamin's `InstrumentedSubstrate` works without this proposal; this proposal would make it richer.
