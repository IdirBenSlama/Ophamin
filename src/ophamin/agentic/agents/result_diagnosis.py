"""Agent: structured scientific diagnosis of a signed proof (or a set).

This is the "analysis and diagnosis must be performed by the agentic
system" capability. It reads one proof — or a *set* of proofs (e.g. the
cross-domain flow map) — and produces a STRUCTURED diagnosis: what the
result means, the construction brief if it refuted, anomalies, confounds,
recommendations, and the next question. Unlike ``proof_brief`` (a free-form
markdown summary), this emits a parseable JSON object that can be attached as
a signed analysis artifact.

Routed to the **dedicated SCIENTIFIC tier** (``result_diagnosis`` task), not
a general model — per the owner's directive that validation/diagnosis wants
a domain-dedicated model.

Hard constraints (per the framework's rules):

- **Never overrides the verdict / threshold / observed value.** The
  diagnosis explains what the result IS; it does not re-decide it.
- **Grounded in the real proof data** — the prompt is built from the actual
  claim / verdict / evidence numbers, never invented.
- **No fallback.** If the model is unreachable the client raises loudly; if
  the model's response can't be parsed as the diagnosis JSON, that's a loud
  error — we do not synthesise a fake diagnosis.
- **Tooling layer only.** This runs AFTER measurement, on an existing signed
  proof. No model ever runs inside the measurement path.

The model call is injectable (``client``), so the deterministic core —
building the grounded prompt and parsing the structured response — is
testable with no live model.
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

_SYSTEM_PROMPT = """You are a scientific results analyst for Ophamin, an
empirical observatory. You diagnose signed Empirical Proof Records — the
output of running a falsifiable scenario against a substrate under test.

A proof carries: proof_id; claim (statement + operationalization + threshold
+ h0/h1); verdict (VALIDATED / REFUTED / INCONCLUSIVE) with observed value +
reasoning; and evidence (pillars with statistic_value + ci/p + detail).

Your diagnosis MUST:

1. NEVER re-decide the verdict. The verdict outcome IS the truth. You explain
   what it means; you never argue it should have been different.
2. Be grounded strictly in the numbers provided — never invent values.
3. If REFUTED or INCONCLUSIVE, give a CONSTRUCTION BRIEF: what the refutation
   reveals about what to build, fix, or refine next (empirical work is
   constructive, not just validating).
4. If VALIDATED, name the next-tier question the result opens.
5. Surface anomalies (anything surprising or internally inconsistent) and
   confounds (alternative explanations the design did not rule out).
6. Be precise and terse. No marketing language.

When given a SET of proofs, diagnose the set as a whole: the pattern across
them, the outliers, what the spread reveals.

OUTPUT FORMAT — return ONLY a single JSON object, no prose around it, with
exactly these keys:

{
  "summary": "<one sentence>",
  "meaning": "<what the result(s) mean, grounded in the numbers>",
  "construction_brief": "<if refuted/inconclusive: what to build/fix/refine; else ''>",
  "anomalies": ["<anomaly>", ...],
  "confounds": ["<unruled-out alternative explanation>", ...],
  "recommendations": ["<concrete next action>", ...],
  "next_question": "<the question this result opens>"
}
"""

_DIAGNOSIS_KEYS = (
    "summary", "meaning", "construction_brief",
    "anomalies", "confounds", "recommendations", "next_question",
)


@dataclass(frozen=True)
class DiagnosisResult:
    """A structured, grounded diagnosis of one or more proofs."""

    diagnosis: dict[str, Any]
    proof_ids: tuple[str, ...]
    n_proofs: int
    model: str
    tier: str
    runtime: str
    latency_ms: float
    call_record_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "diagnosis": self.diagnosis,
            "proof_ids": list(self.proof_ids),
            "n_proofs": self.n_proofs,
            "model": self.model,
            "tier": self.tier,
            "runtime": self.runtime,
            "latency_ms": self.latency_ms,
            "call_record_path": self.call_record_path,
        }


class DiagnosisParseError(RuntimeError):
    """Raised when the model's response is not parseable as diagnosis JSON.

    No-fallback: we surface the raw response for triage rather than
    synthesising a fake diagnosis.
    """

    def __init__(self, message: str, *, raw: str = "") -> None:
        super().__init__(message)
        self.raw = raw


def _normalize_proofs(
    proofs: dict[str, Any] | str | Path | list[Any],
) -> list[dict[str, Any]]:
    """Accept a single proof (dict/json/path) or a list; return list of dicts."""
    items = proofs if isinstance(proofs, list) else [proofs]
    out: list[dict[str, Any]] = []
    for p in items:
        if isinstance(p, (str, Path)) and Path(str(p)).is_file():
            out.append(json.loads(Path(str(p)).read_text(encoding="utf-8")))
        elif isinstance(p, str):
            out.append(json.loads(p))
        elif isinstance(p, dict):
            out.append(p)
        else:
            raise TypeError(f"unsupported proof input type: {type(p).__name__}")
    if not out:
        raise ValueError("no proofs given to diagnose")
    return out


def summarize_proof(proof_dict: dict[str, Any]) -> dict[str, Any]:
    """Compact, grounded summary of one proof for the diagnosis prompt.

    Deterministic — testable with no model. Pulls only the real fields the
    diagnosis must rest on.
    """
    claim = proof_dict.get("claim", {}) or {}
    verdict = proof_dict.get("verdict", {}) or {}
    evidence = proof_dict.get("evidence", []) or []
    return {
        "proof_id": str(proof_dict.get("proof_id", ""))[:16],
        "claim_statement": claim.get("statement", ""),
        "threshold": claim.get("threshold", {}),
        "verdict_outcome": verdict.get("outcome", ""),
        "verdict_observed": verdict.get("observed_value", verdict.get("observed")),
        "verdict_reasoning": verdict.get("reasoning", ""),
        "evidence": [
            {
                "statistic_name": e.get("statistic_name", ""),
                "statistic_value": e.get("statistic_value"),
                "ci_low": e.get("ci_low"),
                "ci_high": e.get("ci_high"),
                "p_value": e.get("p_value"),
            }
            for e in evidence[:4]
        ],
    }


def build_diagnosis_messages(summaries: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Build the (system, user) messages from grounded proof summaries.

    Deterministic — testable with no model.
    """
    n = len(summaries)
    header = (
        f"Diagnose this set of {n} Ophamin proofs as a whole."
        if n > 1 else
        "Diagnose this Ophamin proof."
    )
    user = (
        header + " Return ONLY the diagnosis JSON object.\n\n"
        "PROOFS (JSON):\n```json\n"
        + json.dumps(summaries, indent=2)
        + "\n```\n\nDiagnosis JSON:"
    )
    return [
        {"role": "system", "content": zetetic_system(_SYSTEM_PROMPT)},
        {"role": "user", "content": user},
    ]


def parse_diagnosis(response_text: str) -> dict[str, Any]:
    """Parse the model's response into the structured diagnosis.

    Deterministic — testable with no model. Strips markdown fences, extracts
    the JSON object, and normalises the seven keys. No-fallback: a response
    that has no parseable JSON object raises :class:`DiagnosisParseError`.
    """
    text = (response_text or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    # Extract the outermost JSON object.
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise DiagnosisParseError(
            "model response contained no JSON object", raw=response_text)
    try:
        obj = json.loads(text[start:end + 1])
    except ValueError as exc:
        raise DiagnosisParseError(
            f"diagnosis JSON did not parse: {exc}", raw=response_text) from exc
    if not isinstance(obj, dict):
        raise DiagnosisParseError(
            "diagnosis JSON was not an object", raw=response_text)
    # Normalise to the seven keys (missing list-keys -> [], missing str -> "").
    out: dict[str, Any] = {}
    for k in _DIAGNOSIS_KEYS:
        v = obj.get(k)
        if k in ("anomalies", "confounds", "recommendations"):
            out[k] = [str(x) for x in v] if isinstance(v, list) else []
        else:
            out[k] = str(v) if v is not None else ""
    return out


def diagnose(
    proofs: dict[str, Any] | str | Path | list[Any],
    *,
    client: LLMClient | None = None,
    audit: bool = True,
    proofs_root: str = "proofs",
    temperature: float = 0.2,
) -> DiagnosisResult:
    """Produce a structured scientific diagnosis of one proof or a set.

    ``client`` is injectable (a fake in tests; the real
    :class:`LLMClient` in production). The model is the dedicated SCIENTIFIC
    tier via ``pick_model("result_diagnosis")``. No-fallback throughout.
    """
    proof_dicts = _normalize_proofs(proofs)
    summaries = [summarize_proof(p) for p in proof_dicts]
    proof_ids = tuple(s["proof_id"] for s in summaries)
    messages = build_diagnosis_messages(summaries)

    mc = pick_model("result_diagnosis")
    if client is None:
        # Honour a tier routed to an external API; otherwise the local default.
        if mc.provider.value == "external_api" and mc.base_url:
            import os
            api_key = os.environ.get(mc.api_key_env, "") if mc.api_key_env else ""
            client = LLMClient(base_url=mc.base_url, api_key=api_key or "ollama")
        else:
            client = LLMClient()

    resp: LLMResponse = client.chat(
        model=mc.model, messages=messages,
        max_tokens=mc.max_tokens, temperature=temperature,
    )
    content = resp.content or ""
    if not content.strip() and resp.reasoning.strip():
        content = resp.reasoning  # reasoning-tuned model put JSON in reasoning
    diagnosis = parse_diagnosis(content)

    call_path = ""
    if audit:
        rec = LLMCallRecord(
            task="result_diagnosis", runtime=client.runtime_hint,
            model=mc.model, messages=messages,
            max_tokens=mc.max_tokens, temperature=temperature,
            response_format="json",
            content=resp.content, finish_reason=resp.finish_reason,
            prompt_tokens=resp.prompt_tokens,
            completion_tokens=resp.completion_tokens,
            latency_ms=resp.latency_ms,
            ophamin_version=__version__,
        )
        call_path = str(persist_call(rec, proofs_root=proofs_root))

    return DiagnosisResult(
        diagnosis=diagnosis,
        proof_ids=proof_ids,
        n_proofs=len(proof_dicts),
        model=mc.model,
        tier=mc.tier.value,
        runtime=client.runtime_hint,
        latency_ms=resp.latency_ms,
        call_record_path=call_path,
    )
