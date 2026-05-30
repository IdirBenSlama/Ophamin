"""Plain-language significance — what a proof MEANS about Kimera, for a reader
who cannot (and should not have to) read the substrate's code.

Ophamin's first purpose is legibility: the proof corpus must explain Kimera
*itself*, not leave the meaning in a couple of hand-authored briefs. This module
is the default render shape of that explanation — a deterministic, verdict-aware,
per-scenario plain-language paragraph the renderers surface *above* the technical
record, so the corpus explains itself.

It is **authored, with no model in the loop**: each entry is a scenario's meaning
in the owner's "landscape vs filing cabinet" voice, with a branch per outcome
(VALIDATED / REFUTED / INCONCLUSIVE). A proof whose metric has no entry yields no
section — an honest gap, never a fabricated meaning.

Keyed by the claim's pre-registered **threshold metric** — the stable identity of
what a scenario measures. Extend by adding an entry; the owner is the authority
on the wording (these translate the substrate's behaviour into the world's
language, which is meaning-work, not mechanism).
"""

from __future__ import annotations

from typing import Any

# metric -> {"what": <what it tests>, "<OUTCOME>": <plain reading>}
_SIGNIFICANCE: dict[str, dict[str, str]] = {
    "memory_path_dependence": {
        "what": "whether memory is permanent — whether the same thing, seen "
                "again, lands on a deeper groove every time and never resets",
        "VALIDATED": "It does: re-exposure keeps deepening the manifold and the "
                     "scar never resets. Memory accumulates; it does not overwrite.",
        "REFUTED": "It did not here: re-exposure stopped deepening — the manifold "
                   "reset or plateaued, against the accumulation rule.",
        "INCONCLUSIVE": "Too few resolved re-exposures to tell yet.",
    },
    "order_hysteresis": {
        "what": "whether Kimera remembers the ORDER things happened, not just "
                "what happened — a filing cabinet (order-blind) versus a "
                "landscape you walk, where the path leaves a groove",
        "VALIDATED": "It does: the same query, after the same documents in a "
                     "different order, lands differently. Kimera carries the order "
                     "of experience where retrieval carries only the inventory.",
        "REFUTED": "It did not here: accumulation came out order-independent — the "
                   "differentiator is permanence and path-depth, not order.",
        "INCONCLUSIVE": "Not enough signal yet — too few probes resolved, or the "
                        "order effect was not separable from run-noise.",
    },
    "recognition_jaccard_floor": {
        "what": "whether the substrate reliably re-recognises what it has already "
                "deformed around — whether experience leaves a stable imprint, "
                "not noise",
        "VALIDATED": "It does: re-exposed inputs land on the same deformed region. "
                     "The imprint is stable — memory as a shape, not a lookup.",
        "REFUTED": "It did not: re-exposure scattered — the deformation was not "
                   "stable enough to re-recognise.",
        "INCONCLUSIVE": "Too few re-exposure pairs resolved to tell yet.",
    },
    "memory_lift": {
        "what": "whether a partial cue pulls back the rest of an experience — "
                "recall by resonance, the way a smell brings back a whole scene",
        "VALIDATED": "It does: a cue lifts the associated memory above the un-cued "
                     "baseline. The landscape leads you back along the groove.",
        "REFUTED": "It did not here: the cue gave no lift over baseline — no "
                   "associative pull.",
        "INCONCLUSIVE": "Not enough cued trials resolved to tell yet.",
    },
    "history_separation_advantage": {
        "what": "whether Kimera can tell apart two histories made of the SAME "
                "events that ended very differently (crashed-then-recovered "
                "versus rose-then-fell) — the thing order-blind retrieval conflates",
        "VALIDATED": "It can: it separates the two where a set-based retriever sees "
                     "them as identical. Where the order carries the risk, Kimera "
                     "is not blind.",
        "REFUTED": "It could not here: the two histories collapsed together, as "
                   "they do for retrieval.",
        "INCONCLUSIVE": "Not enough paired histories resolved to tell yet.",
    },
    "drawdown_tracking_rho": {
        "what": "whether Kimera measures HOW MUCH worse one history is, not just "
                "that it differs — a magnitude readout, not only a discriminator",
        "VALIDATED": "It does: an internal signal tracks the magnitude of the "
                     "drawdown. The size-meter is live.",
        "REFUTED": "It does not track magnitude here — it tells histories apart, "
                   "but not yet how much worse one is.",
        "INCONCLUSIVE": "Open and honest: Kimera tells histories apart but does not "
                        "yet measure how much worse one is — no working size-meter "
                        "today. This is the gap the magnitude work targets.",
    },
    "phi_floor": {
        "what": "whether the substrate stays integrated — its parts keep acting as "
                "one whole (Φ above a floor) rather than fragmenting",
        "VALIDATED": "It holds: integration stays above the floor across the run — "
                     "the system remains one body.",
        "REFUTED": "It dropped below the floor — integration was not maintained here.",
        "INCONCLUSIVE": "Not enough cycles resolved to tell yet.",
    },
}


def plain_significance(record: dict[str, Any]) -> str | None:
    """A plain-language "what this means about Kimera" paragraph, or ``None``.

    Reads the proof record's pre-registered metric + verdict and returns the
    authored, verdict-aware meaning for that scenario. ``None`` when the metric
    has no authored entry (an honest gap — the renderer omits the section rather
    than inventing a meaning).
    """
    claim = record.get("claim") or {}
    threshold = claim.get("threshold") or {}
    metric = threshold.get("metric")
    entry = _SIGNIFICANCE.get(str(metric)) if metric else None
    if not entry:
        return None
    verdict = record.get("verdict") or {}
    outcome = str(verdict.get("outcome", "")).upper()
    reading = entry.get(outcome)
    if not reading:
        return None
    observed = verdict.get("observed_value")
    tail = f" (observed {metric} = {observed})" if observed is not None else ""
    return f"This proof tests {entry['what']}. {reading}{tail}"


def has_significance(metric: str | None) -> bool:
    """Whether an authored meaning exists for a metric (coverage/tooling)."""
    return bool(metric) and str(metric) in _SIGNIFICANCE
