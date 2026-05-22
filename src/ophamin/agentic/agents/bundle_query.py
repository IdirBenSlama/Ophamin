"""Agent: convert a natural-language query into a bundle filter spec.

The LLM doesn't execute code — it emits a structured filter dict
that :func:`apply_filter` then runs against
:func:`ophamin.http_api.bundle_browser.bundle_tree` output. This
keeps the substrate safe (no arbitrary code execution from NL) AND
makes the filter spec testable/auditable.

Filter spec shape::

    {
        "tier":      "scientific" | "engineering" | ... | null,
        "scenario":  "<scenario-name>" | null,
        "verdict":   "validated" | "refuted" | "inconclusive" | null,
        "since":     "YYYY-MM-DD" | null,
        "until":     "YYYY-MM-DD" | null,
        "n_limit":   <int> | null
    }

FAST tier (llama3.1:8b default) — NL → small JSON is small-model work.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ophamin import __version__
from ophamin.agentic.audit import LLMCallRecord, persist_call
from ophamin.agentic.client import LLMClient, LLMResponse
from ophamin.agentic.models import pick_model
from ophamin.agentic.persona import zetetic_system


_VALID_TIERS = {"scientific", "engineering", "philosophical",
                "empirical_deep", "measurement_machinery"}
_VALID_VERDICTS = {"validated", "refuted", "inconclusive"}


_SYSTEM_PROMPT = """You convert natural-language queries about Ophamin signed
proof bundles into a structured filter spec.

The proof tree on disk is organized:
    proofs/<tier>/<scenario>/<YYYY-MM-DD>_<verdict>_<short-hash>/

Valid tiers: scientific, engineering, philosophical, empirical_deep,
measurement_machinery.
Valid verdicts: validated, refuted, inconclusive.

OUTPUT FORMAT: a JSON object with exactly these keys (use null for
unset fields):

    {
      "tier": "<tier>" | null,
      "scenario": "<scenario-name>" | null,
      "verdict": "<verdict>" | null,
      "since": "YYYY-MM-DD" | null,
      "until": "YYYY-MM-DD" | null,
      "n_limit": <int> | null
    }

Rules:
- Return ONLY the JSON object, no prose.
- If the query says "all", set every field to null.
- "this week" / "last 7 days" -> set "since" to today minus 7 days.
- "validated" / "passed" -> verdict=validated.
- "refuted" / "failed" -> verdict=refuted.
- If the query mentions a scenario name (kebab-case), set scenario.
- If the query says "top N" / "first N", set n_limit=N.
- Unknown / unparseable queries: return all-null but include a "_note"
  key explaining what wasn't understood.
"""


@dataclass(frozen=True)
class BundleQueryResult:
    filter_spec: dict[str, Any]
    raw_response: str
    model: str
    runtime: str
    latency_ms: float
    call_record_path: str


def parse_query(
    query: str,
    *,
    today: str = "",
    client: LLMClient | None = None,
    audit: bool = True,
    proofs_root: str = "proofs",
) -> BundleQueryResult:
    """Convert a natural-language query into a filter-spec dict.

    Parameters
    ----------
    query:
        The natural-language question, e.g.
        ``"show validated proofs from the scientific tier this week"``.
    today:
        Optional YYYY-MM-DD override for "today". When empty, the LLM
        is told to use ``datetime.now`` in its output. Set this in
        tests for determinism.
    """
    if client is None:
        client = LLMClient()
    mc = pick_model("bundle_query")

    user_prompt = f"Today: {today or 'use real today'}\n\nQuery: {query}\n\nFilter spec:"
    messages = [
        {"role": "system", "content": zetetic_system(_SYSTEM_PROMPT)},
        {"role": "user", "content": user_prompt},
    ]
    resp: LLMResponse = client.chat(
        model=mc.model, messages=messages,
        max_tokens=mc.max_tokens, temperature=0.0,
        response_format="json_object",
    )

    spec: dict[str, Any] = {}
    try:
        parsed = json.loads(resp.content)
        if isinstance(parsed, dict):
            spec = _sanitize_spec(parsed)
    except (json.JSONDecodeError, TypeError):
        spec = {}

    call_path = ""
    if audit:
        rec = LLMCallRecord(
            task="bundle_query", runtime=client.runtime_hint,
            model=mc.model, messages=messages,
            max_tokens=mc.max_tokens, temperature=0.0,
            response_format="json_object",
            content=resp.content, finish_reason=resp.finish_reason,
            prompt_tokens=resp.prompt_tokens,
            completion_tokens=resp.completion_tokens,
            latency_ms=resp.latency_ms,
            ophamin_version=__version__,
        )
        call_path = str(persist_call(rec, proofs_root=proofs_root))

    return BundleQueryResult(
        filter_spec=spec,
        raw_response=resp.content,
        model=mc.model,
        runtime=client.runtime_hint,
        latency_ms=resp.latency_ms,
        call_record_path=call_path,
    )


def _sanitize_spec(parsed: dict[str, Any]) -> dict[str, Any]:
    """Coerce LLM output to a safe filter spec.

    - Drop unknown keys (except ``_note``).
    - Validate tier / verdict are in the allowed sets.
    - Validate date format (YYYY-MM-DD).
    - Coerce n_limit to int.
    """
    out: dict[str, Any] = {
        "tier": None, "scenario": None, "verdict": None,
        "since": None, "until": None, "n_limit": None,
    }
    if "_note" in parsed:
        out["_note"] = str(parsed["_note"])
    tier = parsed.get("tier")
    if isinstance(tier, str) and tier in _VALID_TIERS:
        out["tier"] = tier
    scenario = parsed.get("scenario")
    if isinstance(scenario, str) and scenario.strip():
        out["scenario"] = scenario.strip().lower()
    verdict = parsed.get("verdict")
    if isinstance(verdict, str) and verdict.lower() in _VALID_VERDICTS:
        out["verdict"] = verdict.lower()
    import re
    for date_key in ("since", "until"):
        val = parsed.get(date_key)
        if isinstance(val, str) and re.match(r"^\d{4}-\d{2}-\d{2}$", val):
            out[date_key] = val
    n_limit = parsed.get("n_limit")
    if isinstance(n_limit, (int, float)) and n_limit > 0:
        out["n_limit"] = int(n_limit)
    return out


def apply_filter(
    tree: dict[str, Any],
    spec: dict[str, Any],
) -> list[dict[str, Any]]:
    """Apply a parsed filter spec to a ``bundle_tree()`` result.

    Returns a flat list of bundle dicts (each with tier + scenario +
    date + verdict + short_hash + path), matched + truncated per spec.
    """
    out: list[dict[str, Any]] = []
    for tier in tree.get("tiers", []):
        if spec.get("tier") and tier["tier"] != spec["tier"]:
            continue
        for sc in tier.get("scenarios", []):
            if spec.get("scenario") and sc["scenario"] != spec["scenario"]:
                continue
            for b in sc.get("bundles", []):
                if spec.get("verdict") and b["verdict"] != spec["verdict"]:
                    continue
                if spec.get("since") and b["date"] < spec["since"]:
                    continue
                if spec.get("until") and b["date"] > spec["until"]:
                    continue
                out.append({
                    "tier": tier["tier"],
                    "scenario": sc["scenario"],
                    **b,
                })
    n_limit = spec.get("n_limit")
    if isinstance(n_limit, int) and n_limit > 0:
        out = out[:n_limit]
    return out
