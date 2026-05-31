"""Retrieval grounding for the advisory chat (``POST /chat``).

Assembles a small, REAL context from Ophamin's own data — the scenario registry
(claims / goals / falsification consequences), the signed-proof tree (latest
verdict per scenario), the observed value from each scenario's latest signed
proof, and the authored plain-language significance — and returns the entries
most relevant to a question by lexical token overlap.

The chat LLM answers from THIS context, so the proofs / verdicts / numbers it
cites are real (or it says it does not know). The corpus is ~54 scenarios, so
token overlap is enough: no embeddings, no vector store, deterministic, and
dependency-free.

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


def _tokens(text: str) -> set[str]:
    return {
        t for t in _TOKEN.findall((text or "").lower())
        if len(t) > 2 and t not in _STOP
    }


def _observed_for(path: str, proofs_root: str = "proofs") -> Any:
    """The observed value from a bundle's signed ``proof.json`` (or ``None``).

    The proof tree carries the verdict but not the measured value; that lives in
    the signed record. Best-effort read — a missing/garbled file yields ``None``
    so the rest of the context still renders.
    """
    if not path:
        return None
    f = Path(proofs_root) / path / "proof.json"
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    verdict = data.get("verdict") if isinstance(data, dict) else None
    return verdict.get("observed_value") if isinstance(verdict, dict) else None


def build_corpus() -> list[dict[str, Any]]:
    """Per-scenario real records: name / family / tier / goal / falsification +
    the latest signed verdict (and its bundle path) from the proof tree.

    Verdicts are best-effort: if the proof tree can't be read the scenarios are
    still returned (without verdicts) so retrieval keeps working.
    """
    listing = list_scenarios_impl()
    scenarios = listing.get("scenarios", []) if isinstance(listing, dict) else []

    latest_by_scenario: dict[str, dict[str, str]] = {}
    try:
        tree = bundle_tree("proofs")
    except (OSError, ValueError, KeyError):
        tree = {}
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
    return corpus


def retrieve(
    question: str, corpus: list[dict[str, Any]], k: int = 4
) -> list[dict[str, Any]]:
    """Top-``k`` scenarios by token overlap with name / family / goal /
    falsification. A name-token match is weighted heavily — asking about a
    scenario by name should surface it.
    """
    q = _tokens(question)
    if not q or not corpus:
        return []
    scored: list[tuple[int, dict[str, Any]]] = []
    for rec in corpus:
        name_toks = _tokens(rec["name"].replace("-", " "))
        body_toks = _tokens(" ".join([rec["family"], rec["goal"], rec["falsification"]]))
        score = 4 * len(q & name_toks) + len(q & body_toks)
        if score > 0:
            scored.append((score, rec))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [rec for _, rec in scored[:k]]


def format_context(records: list[dict[str, Any]]) -> str:
    """Render retrieved scenarios as a grounding block: goal + claim + threshold
    + latest verdict + observed value + authored significance. Real data only.
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
            observed = _observed_for(r.get("path", ""))
            obs_str = f"  (observed value: {observed})" if observed is not None else ""
            lines.append(f"  latest signed verdict: {str(verdict).upper()}{obs_str}")
            if metric:
                sig = plain_significance({
                    "claim": {"threshold": {"metric": metric}},
                    "verdict": {"outcome": str(verdict).upper(), "observed_value": observed},
                })
                if sig:
                    lines.append(f"  what it means: {sig}")
        blocks.append("\n".join(lines))
    return "\n".join(blocks)


def ground(question: str, k: int = 4) -> str:
    """One-shot grounding: build → retrieve → format. Returns a context block,
    or ``""`` when nothing matches or a source is unavailable.

    Best-effort: never raises. Grounding the chat must not be able to break the
    chat — and if it can't read real data, it returns nothing rather than
    anything invented.
    """
    try:
        return format_context(retrieve(question, build_corpus(), k))
    except Exception:  # noqa: BLE001 — best-effort enrichment; chat degrades to seeded facts, never to fabrication
        return ""
