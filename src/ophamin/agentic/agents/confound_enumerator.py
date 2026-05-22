"""Agent: red-team a VALIDATED proof by enumerating confounds.

Per CLAUDE.md's zetetic-unit principle: validation is the START of
the inquiry, not the end. A VALIDATED proof at threshold T can mean
the substrate genuinely has property X — OR it can mean any of
several confounds (encoder caching, deterministic dispatch, prompt
overlap, recognition-cache hit, sampling artifact, ...). This agent
enumerates the alternatives + proposes a disambiguating follow-up
test for each.

Sister to refuted_triage:

- refuted_triage  : given REFUTED proof → propose next-tier claims
                    that build on the surfaced behavior
- confound_enumerator : given VALIDATED proof → propose alternative
                        explanations + how to test each

The agent NEVER overrides the original verdict. Confounds are flags
for follow-up, not retroactive verdict edits.

REASONING tier — generating plausible confounds + disambiguating
tests requires substantive reasoning across the experimental setup.
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


_SYSTEM_PROMPT = """You are a zetetic confound enumerator. A VALIDATED
Ophamin proof has been handed to you. Your job is to red-team it by
listing 3-5 ALTERNATIVE EXPLANATIONS that could produce the same
observed result WITHOUT the substrate property the claim asserts.

For each confound, also propose a CONCRETE disambiguating follow-up
test — one that would tell apart the substrate-explanation from this
confound. The follow-up does not have to be a full scenario draft;
a one-sentence description is enough.

What counts as a confound:

- Caching / determinism artifacts (the system returned the same answer
  because it cached, not because it computed the same thing).
- Encoder / tokenization artifacts (the metric measures the encoder
  rather than the substrate).
- Selection bias in the corpus / stimuli (the test items were biased
  toward the claim).
- Statistical artifacts (small N, multiple-comparison without
  correction, bootstrap that doesn't recover the population).
- Implementation accidents (a hardcoded threshold, a stub method, a
  silent fallback that masks failure as success).
- Recognition vs computation (the system recognized a fingerprint
  rather than recomputing from scratch).
- Order / sequence effects (the test items came in an order that
  favored the claim).
- Out-of-distribution generalization that the claim implicitly assumes
  but the corpus doesn't test.

What does NOT count as a confound (and should NOT be listed):

- "The substrate could have been different." Not falsifiable.
- "The model's parameters could have been different." Not actionable.
- Generic skepticism ("we can't be sure"). Be specific.
- Re-litigating the verdict ("maybe it's actually REFUTED"). The
  verdict is the verdict; confounds are about INTERPRETATION.

OUTPUT FORMAT: a JSON object with this shape:
  {
    "confounds": [
      {
        "name": "short kebab-case label",
        "mechanism": "1-2 sentence description of how the confound
                      could produce the observed result without the
                      claimed substrate property",
        "disambiguating_test": "1 sentence: what experimental shape
                                would tell apart substrate from confound"
      },
      ...
    ]
  }

Do NOT wrap the JSON in markdown fences. Do NOT add prose around it.
"""


@dataclass(frozen=True)
class ConfoundEnumerationResult:
    confounds: list[dict[str, Any]] = field(default_factory=list)
    raw_response: str = ""
    model: str = ""
    runtime: str = ""
    latency_ms: float = 0.0
    call_record_path: str = ""


def enumerate_confounds(
    proof: dict[str, Any] | str | Path,
    *,
    n_max: int = 5,
    client: LLMClient | None = None,
    audit: bool = True,
    proofs_root: str = "proofs",
    accept_reasoning: bool = False,
) -> ConfoundEnumerationResult:
    """Generate confound proposals for a VALIDATED proof.

    Parameters
    ----------
    proof:
        Either the parsed proof dict, raw JSON string, or path to a
        ``proof.json``. Same shape as ``EmpiricalProofRecord.to_dict()``.
    n_max:
        Cap on returned confounds (model may produce fewer).
    client:
        Optional pre-built LLMClient.
    audit:
        Persist a signed LLMCallRecord.
    accept_reasoning:
        Same opt-in as refuted_triage; last-resort JSON extract from
        reasoning_content channel.

    Returns
    -------
    ConfoundEnumerationResult. On malformed JSON, confounds = [] and
    raw_response is preserved.
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
        raise TypeError(
            f"unsupported proof input type: {type(proof).__name__}",
        )

    claim = proof_dict.get("claim", {})
    verdict = proof_dict.get("verdict", {})
    evidence = proof_dict.get("evidence", []) or []
    data = proof_dict.get("data", {})

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
            {k: e.get(k) for k in (
                "pillar", "statistic_name", "statistic_value",
                "ci_low", "ci_high", "p_value", "detail",
            )}
            for e in evidence[:3]
        ],
        "data_substrate": data.get("substrate_name", ""),
        "data_datasets": [
            {"name": d.get("name", ""), "n_records": d.get("n_records"),
             "kind": d.get("kind", "")}
            for d in (data.get("datasets") or [])[:3]
        ],
    }

    user_prompt = (
        f"VALIDATED proof. Enumerate up to {n_max} confounds that could "
        f"explain the observed result WITHOUT the substrate property "
        f"the claim asserts. For each, propose a disambiguating test.\n\n"
        "PROOF SUMMARY (JSON):\n```json\n"
        + json.dumps(summary, indent=2, default=str)
        + "\n```\n\nReturn the JSON object as specified."
    )

    mc = pick_model("confound_enumerator")
    messages = [
        {"role": "system", "content": zetetic_system(_SYSTEM_PROMPT)},
        {"role": "user", "content": user_prompt},
    ]
    resp: LLMResponse = client.chat(
        model=mc.model, messages=messages,
        max_tokens=mc.max_tokens, temperature=0.5,
        response_format="json_object",
    )

    confounds: list[dict[str, Any]] = []
    try:
        parsed = json.loads(resp.content)
        if isinstance(parsed, dict) and isinstance(parsed.get("confounds"), list):
            confounds = parsed["confounds"][:n_max]
    except (json.JSONDecodeError, TypeError):
        pass

    # Reasoning-channel last-resort (opt-in).
    if not confounds and accept_reasoning and resp.reasoning.strip():
        try:
            text = resp.reasoning.strip()
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end > start:
                parsed = json.loads(text[start:end + 1])
                if isinstance(parsed, dict) and isinstance(parsed.get("confounds"), list):
                    confounds = parsed["confounds"][:n_max]
        except (json.JSONDecodeError, TypeError):
            pass

    call_path = ""
    if audit:
        rec = LLMCallRecord(
            task="confound_enumerator", runtime=client.runtime_hint,
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

    return ConfoundEnumerationResult(
        confounds=confounds,
        raw_response=resp.content,
        model=mc.model,
        runtime=client.runtime_hint,
        latency_ms=resp.latency_ms,
        call_record_path=call_path,
    )
