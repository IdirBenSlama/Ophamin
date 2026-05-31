"""Retrieval grounding for the advisory chat (``POST /chat``).

Assembles a REAL context from Ophamin's own data — the scenario registry
(claims / goals / falsification consequences), the signed-proof tree (latest
verdict per scenario + corpus totals), each scenario's latest signed
``proof.json`` (the observed value AND the verdict's reasoning), and the authored
plain-language significance — and returns the entries most relevant to a
question by lexical token overlap, plus a one-line corpus snapshot.

The chat LLM answers from THIS context, so the proofs / verdicts / numbers /
reasons it cites are real (or it says it does not know). The corpus is ~54
scenarios, so token overlap is enough: no embeddings, no vector store,
deterministic, and dependency-free.

Best-effort by design: :func:`ground` never raises — if a source can't be read,
the chat degrades to FEWER real facts (and its seeded core facts), never to
fabricated ones.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ophamin.http_api.bundle_browser import bundle_tree
from ophamin.interfaces._impls import get_scenario_claim_impl, list_scenarios_impl
from ophamin.reporting.significance import plain_significance

_TOKEN = re.compile(r"[a-z0-9]+")

#: Tokens too common (or too project-ubiquitous) to discriminate between
#: scenarios — dropped before scoring so retrieval keys on the specific terms.
_STOP = frozenset({
    "the", "and", "for", "what", "why", "how", "does", "did", "was", "were",
    "are", "is", "in", "of", "to", "an", "it", "this", "that", "do", "with",
    "on", "at", "by", "be", "or", "as", "from", "about", "mean", "means",
    "kimera", "ophamin", "swm", "proof", "scenario", "substrate",
})

#: Question-word → verdict it implies, so "what failed?" nudges retrieval toward
#: REFUTED scenarios, "what holds up?" toward VALIDATED, etc.
_VERDICT_INTENT: tuple[tuple[str, str], ...] = (
    ("refut", "refuted"), ("fail", "refuted"), ("broke", "refuted"),
    ("disprov", "refuted"), ("valid", "validated"), ("pass", "validated"),
    ("hold", "validated"), ("confirm", "validated"), ("inconclus", "inconclusive"),
    ("unclear", "inconclusive"),
)

#: Cap a single proof's reasoning text injected into context (keeps the prompt
#: bounded with k records; most reasonings are a sentence or two anyway).
_REASONING_CHARS = 600


def _tokens(text: str) -> set[str]:
    return {
        t for t in _TOKEN.findall((text or "").lower())
        if len(t) > 2 and t not in _STOP
    }


def _proof_fields(path: str, proofs_root: str = "proofs") -> dict[str, Any]:
    """``{observed, reasoning}`` from a bundle's signed ``proof.json``.

    The proof tree carries the verdict but not the measured value or the reason
    it landed; both live in the signed record. Best-effort — a missing/garbled
    file yields ``{observed: None, reasoning: None}`` so context still renders.
    """
    out: dict[str, Any] = {"observed": None, "reasoning": None}
    if not path:
        return out
    f = Path(proofs_root) / path / "proof.json"
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return out
    verdict = data.get("verdict") if isinstance(data, dict) else None
    if isinstance(verdict, dict):
        out["observed"] = verdict.get("observed_value")
        reasoning = verdict.get("reasoning")
        if isinstance(reasoning, str) and reasoning.strip():
            out["reasoning"] = reasoning.strip()[:_REASONING_CHARS]
    return out


def build_corpus() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return ``(records, totals)``.

    ``records`` = per-scenario name / family / tier / goal / falsification + the
    latest signed verdict and its bundle path. ``totals`` = the corpus snapshot
    (proof + scenario counts, verdict distribution) from the proof tree.

    Verdicts/totals are best-effort: if the proof tree can't be read the
    scenarios are still returned (without verdicts) so retrieval keeps working.
    """
    listing = list_scenarios_impl()
    scenarios = listing.get("scenarios", []) if isinstance(listing, dict) else []

    latest_by_scenario: dict[str, dict[str, str]] = {}
    totals: dict[str, Any] = {}
    try:
        tree = bundle_tree("proofs")
    except (OSError, ValueError, KeyError):
        tree = {}
    totals = tree.get("totals", {}) or {}
    for tier in tree.get("tiers", []):
        for s in tier.get("scenarios", []):
            bundles = s.get("bundles") or []
            if not bundles:
                continue
            latest = max(bundles, key=lambda b: b.get("date", ""))
            if latest.get("verdict"):
                latest_by_scenario[s.get("scenario", "")] = {
                    "verdict": latest["verdict"], "path": latest.get("path", ""),
                }

    corpus: list[dict[str, Any]] = []
    for s in scenarios:
        name = s.get("name")
        if not name:
            continue
        latest = latest_by_scenario.get(name) or {}
        corpus.append({
            "name": name,
            "family": s.get("family", ""),
            "tier": s.get("tier", ""),
            "goal": s.get("goal", ""),
            "falsification": s.get("falsification_consequence", ""),
            "verdict": latest.get("verdict"),
            "path": latest.get("path", ""),
        })
    return corpus, totals


def _verdict_intent(question: str) -> str | None:
    ql = question.lower()
    for needle, verdict in _VERDICT_INTENT:
        if needle in ql:
            return verdict
    return None


def retrieve(
    question: str, corpus: list[dict[str, Any]], k: int = 4
) -> list[dict[str, Any]]:
    """Top-``k`` scenarios by token overlap with name / family / goal /
    falsification. A name-token match is weighted heavily; and if the question
    implies a verdict ("what failed?"), matching-verdict scenarios get a nudge.
    """
    q = _tokens(question)
    if not q or not corpus:
        return []
    want = _verdict_intent(question)
    scored: list[tuple[int, dict[str, Any]]] = []
    for rec in corpus:
        name_toks = _tokens(rec["name"].replace("-", " "))
        body_toks = _tokens(" ".join([rec["family"], rec["goal"], rec["falsification"]]))
        score = 4 * len(q & name_toks) + len(q & body_toks)
        if score and want and rec.get("verdict") == want:
            score += 2
        if score > 0:
            scored.append((score, rec))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [rec for _, rec in scored[:k]]


def format_context(records: list[dict[str, Any]]) -> str:
    """Render retrieved scenarios as a grounding block: goal + claim + threshold
    + latest verdict + observed value + the verdict's reasoning + authored
    significance. Real data only.
    """
    blocks: list[str] = []
    for r in records:
        lines = [f"- scenario: {r['name']}  (tier: {r['tier']}, family: {r['family']})"]
        if r.get("goal"):
            lines.append(f"  goal: {r['goal']}")
        metric: str | None = None
        full = get_scenario_claim_impl(r["name"])
        if full.get("claim_available"):
            claim = full.get("claim") or {}
            thr = claim.get("threshold") or {}
            metric = thr.get("metric")
            if claim.get("statement"):
                lines.append(f"  claim: {claim['statement']}")
            if thr:
                units = thr.get("units", "") or ""
                lines.append(
                    f"  threshold: {metric} {thr.get('comparator', '')} "
                    f"{thr.get('value', '')} {units}".rstrip()
                )
        verdict = r.get("verdict")
        if verdict:
            fields = _proof_fields(r.get("path", ""))
            observed = fields["observed"]
            obs_str = f"  (observed value: {observed})" if observed is not None else ""
            lines.append(f"  latest signed verdict: {str(verdict).upper()}{obs_str}")
            if fields["reasoning"]:
                lines.append(f"  why (from the signed proof): {fields['reasoning']}")
            if metric:
                sig = plain_significance({
                    "claim": {"threshold": {"metric": metric}},
                    "verdict": {"outcome": str(verdict).upper(), "observed_value": observed},
                })
                if sig:
                    lines.append(f"  what it means: {sig}")
        blocks.append("\n".join(lines))
    return "\n".join(blocks)


def corpus_summary(totals: dict[str, Any]) -> str:
    """One-line real snapshot of the whole corpus (for big-picture questions)."""
    if not totals:
        return ""
    v = totals.get("verdicts", {}) or {}
    return (
        f"Corpus snapshot (real, signed): {totals.get('bundles', '?')} proofs "
        f"across {totals.get('scenarios', '?')} scenarios — "
        f"{v.get('validated', 0)} validated, {v.get('refuted', 0)} refuted, "
        f"{v.get('inconclusive', 0)} inconclusive."
    )


def ground(question: str, k: int = 4) -> str:
    """One-shot grounding: build → snapshot + retrieve → format. Returns a
    context block, or ``""`` on any failure.

    Best-effort: never raises. Grounding the chat must not be able to break the
    chat — and if it can't read real data, it returns nothing rather than
    anything invented.
    """
    try:
        corpus, totals = build_corpus()
        parts: list[str] = []
        snapshot = corpus_summary(totals)
        if snapshot:
            parts.append(snapshot)
        block = format_context(retrieve(question, corpus, k))
        if block:
            parts.append(block)
        return "\n\n".join(parts)
    except Exception:  # noqa: BLE001 — best-effort enrichment; chat degrades to seeded facts, never to fabrication
        return ""
