"""Agent: scout candidate PyPI packages for a measurement need.

The LLM half of the *discover* stage. Given a measurement need that has no
existing tool (the resolver routed it to *wire* an external toolkit), this agent
proposes candidate package **names** to ground against PyPI.

The boundary — same discipline as scenario_gen's score() stub — is that the
agent stops where fabrication would begin:

    The agent proposes a NAME, an import-name hint, and one line on why it might
    fit. It MUST NOT emit a version, a license, a star count, or a download
    figure. Those are authoritative facts resolved from PyPI by
    :func:`ophamin.interop.tool_discovery.discover_candidates`. A name the agent
    invents that doesn't exist on PyPI is simply dropped — it cannot be
    hallucinated into the pipeline.

So the model is advisory (it narrows the search); the ground truth stays
deterministic and re-checkable. Every call is signed as an LLMCallRecord, like
the other agents.

WORKHORSE tier — broad ecosystem knowledge matters more than chain-of-thought.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from ophamin import __version__
from ophamin.agentic.audit import LLMCallRecord, persist_call
from ophamin.agentic.client import LLMClient, LLMResponse
from ophamin.agentic.models import pick_model
from ophamin.agentic.persona import zetetic_system

_SYSTEM_PROMPT = """You are a tool scout for an empirical-measurement observatory.

Given a measurement NEED that currently has no tool, propose candidate Python
packages (from the open-source ecosystem, installable from PyPI) that could
supply it.

HARD CONSTRAINTS:
- Propose the package's PyPI DISTRIBUTION NAME exactly as it is published
  (e.g. "scikit-learn", "ruptures", "statsmodels").
- You MUST NOT output a version, a license, a star count, or a download count.
  Those are resolved authoritatively from PyPI, not from you. Emitting them is a
  fabrication and a defect.
- If the import name differs from the distribution name (e.g. scikit-learn ->
  sklearn), give it as `import_name`; otherwise leave it "".
- `fit_note`: ONE plain line on why this package fits the need. No marketing.
- Prefer mature, widely-used, permissively-licensed libraries. Do not invent
  packages; if unsure a package exists, propose the most likely real PyPI name
  (non-existent names are dropped by grounding, so a wrong guess is harmless but
  a confident fabrication of metadata is not).

OUTPUT FORMAT: a single JSON object, no prose, no markdown fences:
{"candidates": [{"name": "...", "import_name": "...", "fit_note": "..."}]}
Order best-fit first."""

#: Reuse the same conservative distribution-name shape discovery enforces, so
#: an obviously-malformed proposal is dropped before it reaches the network.
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,213}$")


class ToolScoutError(RuntimeError):
    """The scout's response could not be parsed into candidate proposals."""


@dataclass(frozen=True)
class ToolScoutResult:
    """Proposed candidates (name + hints only) + audit metadata."""

    need: str
    proposed: tuple[dict[str, str], ...]
    model: str
    runtime: str
    latency_ms: float
    call_record_path: str

    @property
    def names(self) -> list[str]:
        return [c["name"] for c in self.proposed]

    @property
    def hints(self) -> dict[str, dict[str, str]]:
        """name -> {import_name, fit_note}, ready for discover_candidates."""
        return {
            c["name"]: {
                "import_name": c.get("import_name", ""),
                "fit_note": c.get("fit_note", ""),
            }
            for c in self.proposed
        }


def _extract_json_object(text: str) -> dict[str, Any]:
    """Pull the first JSON object out of a model response (fence-tolerant)."""
    s = (text or "").strip()
    if s.startswith("```"):
        lines = s.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ToolScoutError(f"no JSON object in scout response: {text[:200]!r}")
    try:
        obj = json.loads(s[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ToolScoutError(f"scout response is not valid JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise ToolScoutError("scout response JSON is not an object")
    return obj


def _clean_proposals(obj: dict[str, Any], n_max: int) -> tuple[dict[str, str], ...]:
    """Validate + normalize the candidate list; drop malformed/over-eager entries.

    Defensively strips any version/license/etc. the model emitted despite the
    contract — only name / import_name / fit_note survive, so a fabricated fact
    can never leak downstream even if the model ignores the instruction.
    """
    raw = obj.get("candidates")
    if not isinstance(raw, list):
        raise ToolScoutError("scout JSON missing a 'candidates' list")
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "")).strip()
        if not _NAME_RE.match(name) or name in seen:
            continue
        seen.add(name)
        out.append({
            "name": name,
            "import_name": str(entry.get("import_name", "")).strip(),
            "fit_note": str(entry.get("fit_note", "")).strip(),
        })
        if len(out) >= n_max:
            break
    return tuple(out)


def scout(
    need: str,
    *,
    n_max: int = 6,
    client: LLMClient | None = None,
    audit: bool = True,
    proofs_root: str = "proofs",
    accept_reasoning: bool = False,
) -> ToolScoutResult:
    """Propose candidate package names for a measurement need.

    The returned :class:`ToolScoutResult` carries proposals (name + import-name
    hint + fit note) — NOT graded candidates. Feed ``.names`` + ``.hints`` to
    :func:`ophamin.interop.tool_discovery.discover_candidates` to ground them
    against PyPI, then evaluate/plan via :mod:`ophamin.interop.tool_acquisition`.

    Raises :class:`ToolScoutError` if the response can't be parsed, and
    propagates :class:`ophamin.agentic.client.LLMClientError` on transport
    failure (no silent empty result).
    """
    if not need or not need.strip():
        raise ValueError("scout need must be a non-empty description")
    if n_max < 1:
        raise ValueError(f"n_max must be >= 1, got {n_max}")
    if client is None:
        client = LLMClient()

    mc = pick_model("tool_scout")
    user_prompt = (
        f"MEASUREMENT NEED:\n{need.strip()}\n\n"
        f"Propose up to {n_max} candidate PyPI packages, best-fit first. "
        "Return ONLY the JSON object per the contract — names + import-name "
        "hints + one-line fit notes. No versions, no licenses."
    )
    messages = [
        {"role": "system", "content": zetetic_system(_SYSTEM_PROMPT)},
        {"role": "user", "content": user_prompt},
    ]

    resp: LLMResponse = client.chat(
        model=mc.model, messages=messages,
        max_tokens=mc.max_tokens, temperature=0.1,
        response_format="json_object",
    )

    body = resp.content.strip()
    if not body and accept_reasoning and resp.reasoning.strip():
        body = resp.reasoning.strip()
    proposed = _clean_proposals(_extract_json_object(body), n_max)

    call_path = ""
    if audit:
        rec = LLMCallRecord(
            task="tool_scout", runtime=client.runtime_hint,
            model=mc.model, messages=messages,
            max_tokens=mc.max_tokens, temperature=0.1,
            response_format="json_object",
            content=resp.content, finish_reason=resp.finish_reason,
            prompt_tokens=resp.prompt_tokens,
            completion_tokens=resp.completion_tokens,
            latency_ms=resp.latency_ms,
            ophamin_version=__version__,
        )
        call_path = str(persist_call(rec, proofs_root=proofs_root))

    return ToolScoutResult(
        need=need.strip(),
        proposed=proposed,
        model=mc.model,
        runtime=client.runtime_hint,
        latency_ms=resp.latency_ms,
        call_record_path=call_path,
    )
