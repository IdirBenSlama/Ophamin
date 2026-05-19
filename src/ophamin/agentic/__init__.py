"""Local-LLM agentic layer for Ophamin.

The framework's empirical-observatory discipline is signed-proof + no
fallback + no LLM-inside-substrate. This layer adds LLM-assisted
*observatory tooling* — adapter generation, proof briefs, REFUTED
triage, natural-language bundle queries — while preserving the
signed-record discipline: every LLM call lands as a signed
:class:`LLMCallRecord` under ``proofs/llm_calls/``, so an
LLM-assisted brief stays as auditable as a normal scenario proof.

Hard constraints (per CLAUDE.md):

- LLM outputs NEVER override a ``Verdict.decide(...)`` result.
- LLMs never sit in any path Kimera's substrate consumes.
- Statistical pillars (scipy / numpy / statsmodels / pingouin) remain
  the oracle for ``*-crosscheck`` scenarios — LLMs never substitute.
- Default off: agents fire only when explicitly invoked via the CLI
  or programmatic API. The signed-proof discipline doesn't depend
  on a model being up.

Two runtimes supported via a single OpenAI-compatible HTTP surface:

- **Ollama** (default; ``OPHAMIN_LLM_BASE_URL=http://localhost:11434/v1``)
- **MLX-LM** (Apple Silicon native; ``OPHAMIN_LLM_BASE_URL=http://localhost:8080/v1``)

Swap by setting the env var; same client code.

Public surface:

- :class:`LLMClient` — OpenAI-compatible chat-completions client
- :func:`pick_model` — task → model routing (fast / workhorse / coder / reasoning)
- :class:`LLMCallRecord` + :func:`persist_call` — signed audit record
- Four agents under :mod:`ophamin.agentic.agents`:
  ``adapter_gen`` / ``proof_brief`` / ``refuted_triage`` / ``bundle_query``
"""

from ophamin.agentic.client import LLMClient, LLMClientError
from ophamin.agentic.models import (
    TaskTier,
    TASK_ROUTING,
    pick_model,
)
from ophamin.agentic.audit import (
    LLMCallRecord,
    persist_call,
)

__all__ = [
    "LLMClient",
    "LLMClientError",
    "TaskTier",
    "TASK_ROUTING",
    "pick_model",
    "LLMCallRecord",
    "persist_call",
]
