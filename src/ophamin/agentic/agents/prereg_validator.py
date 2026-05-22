"""Agent: vet a claim's pre-registration for falsifiability discipline.

Per CLAUDE.md's empirical-loop principle: Ophamin's load-bearing claim
is that every proof is falsifiable. A claim that *looks* falsifiable
but isn't (vague threshold, h0 ≡ h1, metric that the scenario doesn't
actually compute, etc.) silently degrades that contract. This agent
reads a claim BEFORE the scenario runs and surfaces structural
issues that would make the eventual verdict meaningless.

The agent is ADVISORY. It does not block runs. The operator decides
whether to revise or proceed. Severity is a hint, not a veto.

Specifically NOT in scope:

- Verdict decision (Verdict.decide is the only authoritative path).
- Threshold value selection (that's threshold_proposer territory and
  is its own dangerous surface — p-hacking risk).
- Statistical method choice (pillar_picker territory).
- Whether the scenario CODE matches the claim (that's a separate
  agent; this one reads the claim only).

REASONING tier — the checks are semantic (h0/h1 logical opposition,
operationalization concreteness), not syntactic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ophamin import __version__
from ophamin.agentic.audit import LLMCallRecord, persist_call
from ophamin.agentic.client import LLMClient, LLMResponse
from ophamin.agentic.models import pick_model
from ophamin.agentic.persona import zetetic_system


_SYSTEM_PROMPT = """You are a falsifiability auditor for empirical claims.
Given a claim dict (statement + operationalization + threshold + h0 + h1),
flag issues that would make the eventual VALIDATED/REFUTED verdict
meaningless.

Check for:

1. THRESHOLD CONCRETENESS — threshold.value must be numeric. A None /
   "auto" / "TBD" value is not falsifiable.
2. THRESHOLD DIRECTION — comparator must be one of >=, <=, >, <, ==,
   != AND the direction must align with what h1 asserts.
3. H0 vs H1 LOGICAL OPPOSITION — H0 must negate H1; if both could
   simultaneously be true, the verdict is meaningless.
4. OPERATIONALIZATION CONCRETENESS — must name the metric explicitly,
   say HOW it's computed, and on WHAT data. "Test that X is good" is
   not operationalizable.
5. METRIC-CLAIM CONSISTENCY — the metric named in the threshold must
   match the metric described in the operationalization. A claim about
   X with a threshold on Y is malformed.
6. CIRCULARITY — the operationalization must not assume what's being
   tested. "X is true because the scenario reports X = true" is
   tautological.
7. SCOPE CONCRETENESS — must say on what corpus / under what conditions.
   "Under all conditions" is unfalsifiable; "Under condition C with
   N >= 30 records" is.

For each issue, propose a CONCRETE recommendation that would fix it
without re-deciding the underlying scientific question.

Severity rubric:
- "ok"    : no issues; claim is falsifiable as written
- "warn"  : one or more minor issues; the verdict will be interpretable
            but the operator should improve before publishing
- "block" : claim is not falsifiable as written; the verdict would be
            meaningless. Recommend revision before running.

OUTPUT FORMAT: a JSON object with these keys:
  {
    "severity": "ok" | "warn" | "block",
    "is_falsifiable": boolean,
    "issues": [
      {"code": "THRESHOLD_VAGUE" | "H0_H1_OVERLAP" | "OP_VAGUE" |
                "METRIC_MISMATCH" | "CIRCULAR" | "SCOPE_VAGUE" | "OTHER",
       "detail": "concrete description of the problem"}
    ],
    "recommendations": [
      "concrete revision that would fix issue N"
    ]
  }

Do NOT wrap the JSON in markdown fences. Do NOT add prose around it.
"""


@dataclass(frozen=True)
class PreregValidationResult:
    severity: str  # "ok" | "warn" | "block"
    is_falsifiable: bool
    issues: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    raw_response: str = ""
    model: str = ""
    runtime: str = ""
    latency_ms: float = 0.0
    call_record_path: str = ""


def _normalize_claim_input(
    claim: dict[str, Any] | str | Path,
) -> dict[str, Any]:
    """Accept dict / JSON string / proof.json path / claim.json path.

    If given a proof.json (has a top-level "claim" key), extracts the
    nested claim dict. Otherwise expects the input to already be
    the claim dict itself.
    """
    if isinstance(claim, (str, Path)) and Path(str(claim)).is_file():
        loaded = json.loads(Path(str(claim)).read_text())
    elif isinstance(claim, str):
        loaded = json.loads(claim)
    elif isinstance(claim, dict):
        loaded = claim
    else:
        raise TypeError(
            f"unsupported claim input type: {type(claim).__name__}; "
            "expected dict | JSON string | path to JSON file",
        )
    # If we were handed a full proof.json, descend.
    if "claim" in loaded and isinstance(loaded["claim"], dict):
        return loaded["claim"]
    return loaded


def validate_preregistration(
    claim: dict[str, Any] | str | Path,
    *,
    client: LLMClient | None = None,
    audit: bool = True,
    proofs_root: str = "proofs",
    accept_reasoning: bool = False,
) -> PreregValidationResult:
    """Vet a claim for falsifiability discipline.

    Parameters
    ----------
    claim:
        Either a claim dict (statement / operationalization / threshold /
        h0 / h1), a JSON string of one, a path to a JSON file, or a path
        to a full proof.json (the nested "claim" key is auto-extracted).
    client:
        Optional pre-built LLMClient.
    audit:
        Persist a signed LLMCallRecord.
    accept_reasoning:
        When True AND content channel is empty AND reasoning_content
        contains parsable JSON, extract from reasoning. Explicit
        opt-in, same shape as refuted_triage.

    Returns
    -------
    PreregValidationResult with severity, is_falsifiable, issues,
    recommendations, raw_response, and audit metadata.

    On malformed model output: severity defaults to "warn" + an
    "OTHER" issue flagging the parse failure (the operator sees that
    the agent ran but couldn't structure its answer). Never silently
    returns "ok" on parse failure.
    """
    if client is None:
        client = LLMClient()

    claim_dict = _normalize_claim_input(claim)

    user_prompt = (
        "Validate the falsifiability of this claim. Apply the 7 checks.\n\n"
        "CLAIM:\n```json\n"
        + json.dumps(claim_dict, indent=2, default=str)
        + "\n```\n\nReturn the JSON validation object."
    )

    mc = pick_model("prereg_validator")
    messages = [
        {"role": "system", "content": zetetic_system(_SYSTEM_PROMPT)},
        {"role": "user", "content": user_prompt},
    ]
    resp: LLMResponse = client.chat(
        model=mc.model, messages=messages,
        max_tokens=mc.max_tokens, temperature=0.2,
        response_format="json_object",
    )

    parsed: dict[str, Any] | None = None
    try:
        parsed = json.loads(resp.content)
    except (json.JSONDecodeError, TypeError):
        parsed = None

    # Reasoning-channel last-resort (opt-in only).
    if parsed is None and accept_reasoning and resp.reasoning.strip():
        try:
            text = resp.reasoning.strip()
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end > start:
                parsed = json.loads(text[start:end + 1])
        except (json.JSONDecodeError, TypeError):
            parsed = None

    if isinstance(parsed, dict) and "severity" in parsed:
        severity = str(parsed.get("severity", "warn")).lower()
        if severity not in ("ok", "warn", "block"):
            severity = "warn"
        is_falsifiable = bool(parsed.get("is_falsifiable", severity == "ok"))
        issues = list(parsed.get("issues", []) or [])
        recommendations = list(parsed.get("recommendations", []) or [])
    else:
        # Parse failure: surface honestly, do NOT pretend OK.
        severity = "warn"
        is_falsifiable = False
        issues = [{
            "code": "OTHER",
            "detail": "agent response was not parsable as the expected "
                      "JSON object; manual review required",
        }]
        recommendations = [
            "re-run with --accept-reasoning if the routed model is "
            "reasoning-tuned, or route this task to a content-clean "
            "model (e.g. OPHAMIN_AGENT_MODEL_PREREG_VALIDATOR=...)",
        ]

    call_path = ""
    if audit:
        rec = LLMCallRecord(
            task="prereg_validator", runtime=client.runtime_hint,
            model=mc.model, messages=messages,
            max_tokens=mc.max_tokens, temperature=0.2,
            response_format="json_object",
            content=resp.content, finish_reason=resp.finish_reason,
            prompt_tokens=resp.prompt_tokens,
            completion_tokens=resp.completion_tokens,
            latency_ms=resp.latency_ms,
            ophamin_version=__version__,
        )
        call_path = str(persist_call(rec, proofs_root=proofs_root))

    return PreregValidationResult(
        severity=severity,
        is_falsifiable=is_falsifiable,
        issues=issues,
        recommendations=recommendations,
        raw_response=resp.content,
        model=mc.model,
        runtime=client.runtime_hint,
        latency_ms=resp.latency_ms,
        call_record_path=call_path,
    )
