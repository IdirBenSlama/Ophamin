"""Agent: write a contextual plain-English brief for a signed proof.

Reads a proof JSON (signed :class:`EmpiricalProofRecord`) + emits a
2-4 paragraph brief in Markdown. Replaces the templated ``proof.md``
inside a bundle when the operator wants an interpretive summary
rather than a structured field-by-field render.

Important constraints:

- The brief NEVER overrides the verdict / threshold / observed value
  from the proof. It explains what they ARE — it does not re-decide.
- The brief MUST cite the proof_id + scenario name + verdict outcome
  exactly so the audit trail stays unambiguous.
- If the proof is REFUTED or INCONCLUSIVE, the brief surfaces the
  empirical-construction reading (per CLAUDE.md: refuted = design
  brief for the substrate).

WORKHORSE tier (llama3.3:70b default) — general English summarization.
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


_SYSTEM_PROMPT = """You write concise, accurate plain-English briefs for
signed Ophamin Empirical Proof Records.

A "proof" is the output of running a falsifiable scenario against a
substrate. It carries:

- proof_id (SHA-256 content hash)
- claim (statement + operationalization + threshold + h0 + h1)
- verdict (VALIDATED / REFUTED / INCONCLUSIVE) with observed value + reasoning
- evidence (one or more PillarEvidence dicts with statistic_value + ci/p)

Your brief MUST:

1. Open with one sentence that names the scenario, what it tested, and the verdict outcome.
2. Quote the observed value and threshold; explain whether the threshold was met (verdict outcome IS the truth — never argue the verdict).
3. If REFUTED or INCONCLUSIVE, frame as a substrate-construction signal per
   the empirical-loop principle: the refutation reveals what to build next.
4. If VALIDATED, name the next-tier question the result opens.
5. Be precise about numbers — do not round or paraphrase quantitative claims.
6. 2-4 short paragraphs (Markdown). No bullet lists unless they're load-bearing.

OUTPUT FORMAT: pure Markdown text. No code fences around the whole thing.
"""


@dataclass(frozen=True)
class ProofBriefResult:
    brief_markdown: str
    model: str
    runtime: str
    latency_ms: float
    call_record_path: str


def write_brief(
    proof: dict[str, Any] | str | Path,
    *,
    client: LLMClient | None = None,
    audit: bool = True,
    proofs_root: str = "proofs",
) -> ProofBriefResult:
    """Generate a plain-English brief for the given proof.

    Parameters
    ----------
    proof:
        Either the parsed proof dict, raw JSON string, or path to a
        ``proof.json`` file. The same shape ``EmpiricalProofRecord.to_dict()``
        emits.
    client:
        Optional pre-built :class:`LLMClient`.
    audit:
        Persist a signed call record.
    """
    if client is None:
        client = LLMClient()

    # Normalize input to a dict
    if isinstance(proof, (str, Path)) and Path(str(proof)).is_file():
        proof_dict = json.loads(Path(str(proof)).read_text())
    elif isinstance(proof, str):
        proof_dict = json.loads(proof)
    elif isinstance(proof, dict):
        proof_dict = proof
    else:
        raise TypeError(f"unsupported proof input type: {type(proof).__name__}")

    # Compact summary the model can chew on without 100 lines of nesting
    claim = proof_dict.get("claim", {})
    verdict = proof_dict.get("verdict", {})
    evidence = proof_dict.get("evidence", []) or []
    summary = {
        "proof_id": proof_dict.get("proof_id", "")[:16],
        "scenario": (proof_dict.get("preregistration") or {}).get("scenario", "")
                    or claim.get("operationalization", "")[:80],
        "claim_statement": claim.get("statement", ""),
        "threshold": claim.get("threshold", {}),
        "verdict_outcome": verdict.get("outcome", ""),
        "verdict_observed": verdict.get("observed"),
        "verdict_reasoning": verdict.get("reasoning", ""),
        "evidence_pillars": [
            {
                "pillar": e.get("pillar", ""),
                "statistic_name": e.get("statistic_name", ""),
                "statistic_value": e.get("statistic_value"),
                "ci_low": e.get("ci_low"),
                "ci_high": e.get("ci_high"),
                "p_value": e.get("p_value"),
            }
            for e in evidence[:3]  # at most 3 pillars to keep prompt small
        ],
    }
    user_prompt = (
        "Write a 2-4 paragraph plain-English brief for this Ophamin proof.\n\n"
        "PROOF SUMMARY (JSON):\n```json\n"
        + json.dumps(summary, indent=2)
        + "\n```\n\nBrief:"
    )

    mc = pick_model("proof_brief")
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    resp: LLMResponse = client.chat(
        model=mc.model, messages=messages,
        max_tokens=mc.max_tokens, temperature=0.3,
    )

    brief = resp.content.strip()
    # Drop any wrapping markdown fences
    if brief.startswith("```"):
        lines = brief.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        brief = "\n".join(lines)

    call_path = ""
    if audit:
        rec = LLMCallRecord(
            task="proof_brief", runtime=client.runtime_hint,
            model=mc.model, messages=messages,
            max_tokens=mc.max_tokens, temperature=0.3,
            response_format="text",
            content=resp.content, finish_reason=resp.finish_reason,
            prompt_tokens=resp.prompt_tokens,
            completion_tokens=resp.completion_tokens,
            latency_ms=resp.latency_ms,
            ophamin_version=__version__,
        )
        call_path = str(persist_call(rec, proofs_root=proofs_root))

    return ProofBriefResult(
        brief_markdown=brief, model=mc.model, runtime=client.runtime_hint,
        latency_ms=resp.latency_ms, call_record_path=call_path,
    )
