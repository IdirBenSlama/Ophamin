"""Agent: read a REFUTED proof; propose 1-3 follow-up scenario drafts.

Per CLAUDE.md's empirical-construction reading: a REFUTED verdict
isn't a failure — it's a design brief for the next substrate-build
step. This agent operationalizes that: given a REFUTED proof, it
reads the claim + observed + evidence + reasoning, and proposes
1-3 next scenarios that probe the surfaced behavior.

Output is a structured list of follow-up proposals (each with a
claim five-tuple draft). The operator + downstream code review;
this agent never writes a Scenario class directly — it stages
ideas.

REASONING tier (deepseek-r1:32b default) — hypothesis derivation
needs chain-of-thought.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ophamin import __version__
from ophamin.agentic.audit import LLMCallRecord, persist_call
from ophamin.agentic.client import LLMClient, LLMResponse
from ophamin.agentic.models import pick_model
from ophamin.agentic.persona import zetetic_system


_SYSTEM_PROMPT = """You are an empirical-observatory hypothesis generator.
A "REFUTED" Ophamin proof has been handed to you. Your job is to propose
1-3 follow-up scenarios that probe the surfaced behavior.

Per the empirical-construction principle: a refutation reveals what the
substrate's primitives actually do (vs. what was expected). Each follow-up
must convert the refutation into a falsifiable next-step claim — NOT
re-test the same claim with a different threshold.

For each follow-up, produce:

- "title"            : short kebab-case scenario name (1-5 words)
- "claim_statement"  : one sentence, falsifiable, plain English
- "operationalization": how it'd be measured (pillar + metric + estimator)
- "threshold_metric" : the metric name
- "threshold_op"     : one of ">=", "<=", ">", "<", "=="
- "threshold_value"  : a number
- "h0"               : null hypothesis
- "h1"               : alternative hypothesis
- "rationale"        : 1-2 sentences explaining why THIS follow-up

OUTPUT FORMAT: a JSON object with a single key "followups" mapping to
an array of 1-3 objects with the fields above. Do not wrap the JSON
in markdown fences. Do not add prose around it.
"""


@dataclass(frozen=True)
class RefutedTriageResult:
    followups: list[dict[str, Any]]
    raw_response: str
    model: str
    runtime: str
    latency_ms: float
    call_record_path: str


def propose_followups(
    proof: dict[str, Any] | str | Path,
    *,
    n_max: int = 3,
    client: LLMClient | None = None,
    audit: bool = True,
    proofs_root: str = "proofs",
    accept_reasoning: bool = False,
) -> RefutedTriageResult:
    """Generate follow-up scenario proposals for a REFUTED proof.

    Returns a parsed list of proposal dicts. If the model emits
    malformed JSON, the raw response is preserved in ``raw_response``
    and ``followups`` is an empty list — caller decides what to do
    (re-prompt, hand-edit, etc.).

    ``accept_reasoning`` (default False) — when True AND the content
    channel comes back empty AND the reasoning channel contains a
    parsable JSON object (some reasoning-tuned models append the
    final structured answer to ``reasoning_content`` when emit-after-
    think is misconfigured), try the reasoning channel as a last
    resort. Failure here leaves ``followups`` empty (per the
    existing contract — no silent fabrication).
    """
    if client is None:
        client = LLMClient()

    if isinstance(proof, (str, Path)) and Path(str(proof)).is_file():
        proof_dict = json.loads(Path(str(proof)).read_text())
    elif isinstance(proof, str):
        proof_dict = json.loads(proof)
    elif isinstance(proof, dict):
        proof_dict = proof
    else:
        raise TypeError(f"unsupported proof input type: {type(proof).__name__}")

    claim = proof_dict.get("claim", {})
    verdict = proof_dict.get("verdict", {})
    evidence = proof_dict.get("evidence", []) or []
    summary = {
        "proof_id": proof_dict.get("proof_id", "")[:16],
        "claim_statement": claim.get("statement", ""),
        "operationalization": claim.get("operationalization", ""),
        "threshold": claim.get("threshold", {}),
        "h0": claim.get("h0", ""),
        "h1": claim.get("h1", ""),
        "verdict_outcome": verdict.get("outcome", ""),
        "verdict_observed": verdict.get("observed"),
        "verdict_reasoning": verdict.get("reasoning", ""),
        "evidence_pillars": [
            {k: e.get(k) for k in ("pillar", "statistic_name", "statistic_value",
                                    "ci_low", "ci_high", "p_value", "detail")}
            for e in evidence[:3]
        ],
    }

    user_prompt = (
        f"REFUTED proof. Propose up to {n_max} follow-up scenarios.\n\n"
        "PROOF SUMMARY (JSON):\n```json\n"
        + json.dumps(summary, indent=2, default=str)
        + '\n```\n\nReturn the JSON object as specified.'
    )

    mc = pick_model("refuted_triage")
    messages = [
        {"role": "system", "content": zetetic_system(_SYSTEM_PROMPT)},
        {"role": "user", "content": user_prompt},
    ]
    resp: LLMResponse = client.chat(
        model=mc.model, messages=messages,
        max_tokens=mc.max_tokens, temperature=0.5,
        response_format="json_object",
    )

    followups: list[dict[str, Any]] = []
    parse_source = "content"
    try:
        parsed = json.loads(resp.content)
        if isinstance(parsed, dict) and isinstance(parsed.get("followups"), list):
            followups = parsed["followups"][:n_max]
    except (json.JSONDecodeError, TypeError):
        # Leave followups empty; caller can re-prompt.
        pass

    # Reasoning-channel fallback — explicit, opt-in, last resort.
    # Tries to extract a JSON object from reasoning_content (some
    # reasoning models trail the final structured answer here when
    # the emit-after-think turn is truncated).
    if not followups and accept_reasoning and resp.reasoning.strip():
        try:
            # Best-effort: slice from the FIRST '{' to the LAST '}'.
            # The first '{' starts the outermost object; the last
            # '}' closes it. Inner braces (e.g. from nested followup
            # dicts) are correctly preserved inside the slice.
            text = resp.reasoning.strip()
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end > start:
                parsed = json.loads(text[start:end + 1])
                if isinstance(parsed, dict) and isinstance(parsed.get("followups"), list):
                    followups = parsed["followups"][:n_max]
                    parse_source = "reasoning"
        except (json.JSONDecodeError, TypeError):
            pass

    call_path = ""
    if audit:
        rec = LLMCallRecord(
            task="refuted_triage", runtime=client.runtime_hint,
            model=mc.model, messages=messages,
            max_tokens=mc.max_tokens, temperature=0.5,
            response_format="json_object",
            content=resp.content, finish_reason=resp.finish_reason,
            prompt_tokens=resp.prompt_tokens,
            completion_tokens=resp.completion_tokens,
            latency_ms=resp.latency_ms,
            ophamin_version=__version__,
        )
        call_path = str(persist_call(rec, proofs_root=proofs_root))

    return RefutedTriageResult(
        followups=followups,
        raw_response=resp.content,
        model=mc.model,
        runtime=client.runtime_hint,
        latency_ms=resp.latency_ms,
        call_record_path=call_path,
    )
