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

from collections.abc import Iterable
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
    "arrow_detection_rate": {
        "what": "whether Kimera can feel time's arrow — recover which way a real "
                "process actually ran from its exact time-reversal, off its own "
                "path-dependent entropy production, where an order-blind reader cannot",
        "VALIDATED": "It can: it recovers the true temporal direction above chance. "
                     "The substrate's path leaves an arrow that reversal can't hide.",
        "REFUTED": "It could not here: forward and reversed looked alike — no arrow "
                   "recovered above chance.",
        "INCONCLUSIVE": "Not enough resolved trials to tell yet.",
    },
    "number_line_spearman": {
        "what": "whether Kimera's native number sense lays real numbers on a faithful "
                "line — magnitude-ordered, monotone, neighbours-near — straight from "
                "the energy law (E_p = ln p), with no scale imposed from outside",
        "VALIDATED": "It does: bigger numbers land at bigger energies, in order, "
                     "neighbours close. A number line emerges from the substrate's "
                     "own physics.",
        "REFUTED": "It did not here: the ordering broke — magnitude did not map "
                   "monotonically onto the prime energy.",
        "INCONCLUSIVE": "Not enough resolved magnitudes to tell yet.",
    },
    "interoception_fidelity_spearman": {
        "what": "whether the substrate's sense of its OWN internal events is "
                "magnitude-faithful — bigger internal magnitudes landing on ordered "
                "primes, where a name-fingerprint shortcut collapsed it",
        "VALIDATED": "It does: the live internal-event chain orders magnitude "
                     "faithfully. Kimera feels the size of its own states, not just "
                     "their labels.",
        "REFUTED": "It did not here: internal magnitude did not map in order — "
                   "interoception stayed name-shaped, not magnitude-shaped.",
        "INCONCLUSIVE": "Not enough resolved internal events to tell yet.",
    },
    "zero_void_proximity": {
        "what": "whether the number ZERO lands in Kimera's VOID/collapse state rather "
                "than idle rest — whether nothing is felt as absence, not as just "
                "another quiet number",
        "VALIDATED": "It does: zero collocates with the void/collapse state, not idle "
                     "rest. Nothing is felt as nothing — a presence of absence.",
        "REFUTED": "It did not here: zero sat in ordinary rest, not the void — no "
                   "special collapse signature.",
        "INCONCLUSIVE": "Not enough resolved trials to tell yet.",
    },
    "adaptive_vs_generous_recall_ratio": {
        "what": "whether the substrate chooses its OWN geoid dimension as its "
                "concept-cloud grows (N tracking its participation ratio) instead of "
                "a dimension picked by a person — without losing recall",
        "VALIDATED": "It does: a self-determined N tracks the growing concept cloud "
                     "and holds recall near a generously-sized fixed N. The shape is "
                     "found, not assigned.",
        "REFUTED": "It did not here: the self-chosen N lost ground to a fixed generous "
                   "N — self-sizing cost recall.",
        "INCONCLUSIVE": "Not enough growth resolved to tell yet.",
    },
    "aggregate_orphan_rate": {
        "what": "how much of Kimera's own machinery is actually wired in — the share "
                "of canonical components that are NOT orphaned (dead or unreachable)",
        "VALIDATED": "Most of it is wired: the orphan rate sits under the bar. The "
                     "body is connected, not a pile of disconnected parts.",
        "REFUTED": "Too much is orphaned here: the orphan rate exceeded the bar — a "
                   "wiring gap (which is fixable), not necessarily an architectural one.",
        "INCONCLUSIVE": "Not enough of the tree resolved to tell yet.",
    },
    # Prime determinism — single-instance and cross-instance share one meaning.
    "p_identity_invariance_rate": {
        "what": "whether the same concept always gets the same identity prime, so "
                "meaning has a fixed address rather than a random one per run",
        "VALIDATED": "It does: the identity prime is invariant — same concept, same "
                     "prime, every run. Meaning has a stable address.",
        "REFUTED": "It did not here: the identity prime drifted — meaning's address "
                   "was not stable across runs.",
        "INCONCLUSIVE": "Not enough resolved concepts to tell yet.",
    },
    "cross_instance_p_identity_invariance_rate": {
        "what": "whether the same concept gets the same identity prime across "
                "SEPARATE instances — so meaning is shared, not private to one run, "
                "which is what lets Nodes ever pool experience",
        "VALIDATED": "It does: separate instances agree on the identity prime — same "
                     "concept, same address everywhere. The prerequisite for a shared "
                     "memory across Nodes holds.",
        "REFUTED": "It did not here: instances disagreed on the identity prime — "
                   "meaning's address was instance-private, which would block pooling.",
        "INCONCLUSIVE": "Not enough resolved concepts to tell yet.",
    },
    "graded_fidelity_advantage": {
        "what": "whether Kimera measures HOW MUCH worse one history is — grading the "
                "SIZE of the drawdown difference, not just telling histories apart — "
                "above what a plain order-aware reader already manages",
        "VALIDATED": "It does: its manifold-state distance grades the magnitude of "
                     "the drawdown difference above the order-aware bar. A real "
                     "size-meter — telling-apart AND sizing.",
        "REFUTED": "Not yet: it registers the order (which history) but does not grade "
                   "proportional magnitude (how much worse) above the order-aware bar. "
                   "This is the honest magnitude gap — telling-apart works, sizing does "
                   "not on the current readouts.",
        "INCONCLUSIVE": "Too few orderings resolved to tell yet.",
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


def covered_metrics() -> "frozenset[str]":
    """The metrics with an authored plain-language meaning.

    A scenario whose metric is NOT in here renders no 'What this means' section —
    an honest, visible gap. Use this to audit legibility coverage rather than let
    silent omission read as 'covered'.
    """
    return frozenset(_SIGNIFICANCE)


def coverage_report(metrics: Iterable[str]) -> dict[str, Any]:
    """Which of the given scenario metrics carry an authored plain-language meaning.

    Surfaces the legibility gap honestly (no silent caps): pass the corpus's
    pre-registered metrics and get ``{covered, uncovered, fraction}``. Every metric
    in ``uncovered`` renders no 'What this means' today — the explicit to-do list
    for extending the meaning layer, rather than a silent omission that reads as
    'covered'.
    """
    seen = {str(m) for m in metrics if m}
    covered = sorted(m for m in seen if m in _SIGNIFICANCE)
    uncovered = sorted(m for m in seen if m not in _SIGNIFICANCE)
    return {
        "covered": covered,
        "uncovered": uncovered,
        "fraction": len(covered) / len(seen) if seen else 0.0,
    }
