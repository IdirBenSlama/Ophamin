"""A falsifiable permanence metric — probe-specific depth, not a global counter.

The signed `memory-permanence-flow` proof scores "memory is permanent — a
re-exposed probe lands on a strictly-deeper manifold every time" with a metric
that reads the **global** scar count (`vault_stats.total_scars_stored`). That
counter is append-only: it rises every cycle regardless of which probe was
shown or whether anything was actually "remembered". In the genesis proof the
per-step delta is a constant (= the interleave gap), so the metric is ~1.0 for
ANY input that runs — it confirms a counter counts, not that memory is permanent.

This module measures the depth of the **specific re-exposed probe** instead, so
the claim becomes falsifiable: a probe that is recognised but NOT further
deepened yields delta == 0 and does NOT count toward permanence. If Kimera's
memory is genuinely path-dependent at the probe level, this still passes; if the
original result was an artifact of the global counter, this exposes it.

It operates on already-captured per-probe depth observations, so it can be run
offline against a re-instrumented trajectory. (Producing probe-specific depths
requires a live Kimera run — the engine is not in this repo — so wiring this
into a signed re-run is an owner step; the metric + its falsifiability are here.)
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def probe_specific_permanence(
    probe_depths: Sequence[float],
    *,
    strict: bool = True,
) -> dict[str, Any]:
    """Proportion of a probe's re-exposures where ITS OWN depth increased.

    ``probe_depths`` is the manifold depth observed for ONE probe at each of its
    re-exposures, in temporal order. Returns the proportion of consecutive
    transitions where depth increased (``strict``: strictly ``>``; else ``>=``),
    plus the per-transition deltas and ``n_transitions``.

    Unlike the global-scar metric this CAN be < 1.0 — a recognised-but-not-
    deepened re-exposure (delta == 0) does not count. ``permanent`` is True only
    when every transition deepened (proportion == 1.0) over at least one
    transition. With < 2 observations it returns ``assessable=False`` rather
    than a vacuous 1.0 (an unfalsifiable "pass" on no evidence).
    """
    depths = [float(d) for d in probe_depths]
    deltas = [b - a for a, b in zip(depths, depths[1:])]
    n = len(deltas)
    if n == 0:
        return {
            "assessable": False,
            "reason": "need >= 2 re-exposures of the probe to assess permanence",
            "n_transitions": 0,
            "depths": depths,
        }
    deepened = sum(1 for d in deltas if (d > 0.0 if strict else d >= 0.0))
    proportion = deepened / n
    return {
        "assessable": True,
        "proportion_deepened": proportion,
        "permanent": proportion == 1.0,
        "n_transitions": n,
        "deltas": deltas,
        "n_zero_or_negative": sum(1 for d in deltas if d <= 0.0),
        "depths": depths,
        "strict": strict,
    }


def global_counter_is_degenerate(scar_series: Sequence[float]) -> dict[str, Any]:
    """Demonstrate why the global-scar metric is ~1.0 by construction.

    Given the global scar series the original proof recorded, report whether it
    is monotonically non-decreasing (an append-only counter) and whether its
    per-step deltas are constant (a fixed cadence, i.e. independent of input
    content). A monotone series trivially satisfies "strictly deeper every time"
    for any input — so a pass on THIS series is not evidence of memory.
    """
    s = [float(x) for x in scar_series]
    deltas = [b - a for a, b in zip(s, s[1:])]
    monotone = all(d >= 0.0 for d in deltas)
    constant_delta = len(set(round(d, 9) for d in deltas)) <= 1 if deltas else False
    return {
        "monotone_nondecreasing": monotone,
        "constant_delta": constant_delta,
        "delta_value": deltas[0] if (constant_delta and deltas) else None,
        "trivially_permanent": monotone,
        "note": (
            "A monotone append-only counter satisfies 'strictly deeper every "
            "time' for ANY input; a constant delta means the increment tracks "
            "cycle cadence, not content. Use probe_specific_permanence instead."
        ),
    }
