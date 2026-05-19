"""Task → model routing for the Ophamin agent layer.

Four tiers map the task's character to a model class. The model
*name* per tier is operator-configurable via environment vars; the
defaults below assume Ollama-installed models.

| Tier        | Char                              | Default Ollama tag    | RAM (~) |
|-------------|-----------------------------------|-----------------------|---------|
| FAST        | classification / routing / NL→JSON | llama3.1:8b           |  ~9 GB  |
| WORKHORSE   | general agentic work               | llama3.3:70b          | ~42 GB  |
| CODER       | code generation                    | qwen2.5-coder:32b     | ~18 GB  |
| REASONING   | chain-of-thought / synthesis       | deepseek-r1:32b       | ~20 GB  |

The model picked per agentic task lives in :data:`TASK_ROUTING`
below. Override an individual task's model via env var
``OPHAMIN_AGENT_MODEL_<task_upper>`` — e.g.
``OPHAMIN_AGENT_MODEL_ADAPTER_GEN=qwen2.5-coder:7b``.
"""

from __future__ import annotations

import enum
import os
from dataclasses import dataclass


class TaskTier(str, enum.Enum):
    """The four model-class tiers."""

    FAST = "fast"
    WORKHORSE = "workhorse"
    CODER = "coder"
    REASONING = "reasoning"


@dataclass(frozen=True)
class ModelChoice:
    """One task's routed model: tier + concrete model tag + max-tokens hint."""

    tier: TaskTier
    model: str
    max_tokens: int = 2048


#: Per-tier default model names. Overrideable via env vars
#: ``OPHAMIN_LLM_MODEL_FAST`` / ``OPHAMIN_LLM_MODEL_WORKHORSE`` /
#: ``OPHAMIN_LLM_MODEL_CODER`` / ``OPHAMIN_LLM_MODEL_REASONING``.
DEFAULT_TIER_MODELS: dict[TaskTier, str] = {
    TaskTier.FAST: os.environ.get("OPHAMIN_LLM_MODEL_FAST", "llama3.1:8b"),
    TaskTier.WORKHORSE: os.environ.get(
        "OPHAMIN_LLM_MODEL_WORKHORSE", "llama3.3:70b-instruct-q4_K_M",
    ),
    TaskTier.CODER: os.environ.get(
        "OPHAMIN_LLM_MODEL_CODER", "qwen2.5-coder:32b",
    ),
    TaskTier.REASONING: os.environ.get(
        "OPHAMIN_LLM_MODEL_REASONING", "deepseek-r1:32b",
    ),
}


#: Per-task tier assignment. Edit here when adding new agents.
#:
#: Rationale:
#: - adapter_gen     → CODER     (code generation; quality > speed)
#: - proof_brief     → WORKHORSE (general English summarization)
#: - refuted_triage  → REASONING (hypothesis derivation needs CoT)
#: - bundle_query    → FAST      (NL → JSON filter; small + fast)
TASK_ROUTING: dict[str, TaskTier] = {
    "adapter_gen": TaskTier.CODER,
    "proof_brief": TaskTier.WORKHORSE,
    "refuted_triage": TaskTier.REASONING,
    "bundle_query": TaskTier.FAST,
}


#: Per-task max-tokens budget. Override via env
#: ``OPHAMIN_AGENT_MAXTOK_<TASK>`` if a particular task needs longer output.
DEFAULT_MAX_TOKENS: dict[str, int] = {
    "adapter_gen": 4096,      # generated code can be long
    "proof_brief": 2048,
    "refuted_triage": 4096,   # reasoning chains can be long
    "bundle_query": 512,      # JSON filter is small
}


def pick_model(task: str) -> ModelChoice:
    """Return the :class:`ModelChoice` for a given agentic task name.

    Resolution order:

    1. ``OPHAMIN_AGENT_MODEL_<TASK>`` env var — direct model override
       for this specific task. When set, the tier comes from
       :data:`TASK_ROUTING` (for telemetry); the model string is what
       was set.
    2. :data:`TASK_ROUTING` + :data:`DEFAULT_TIER_MODELS` — pick the
       tier mapped to this task, then look up that tier's current
       default model.
    3. Falls back to ``WORKHORSE`` tier if the task name isn't in
       :data:`TASK_ROUTING` (defensive — surfaces a misconfigured
       task name as a warning rather than crashing).

    Max-tokens budget comes from :data:`DEFAULT_MAX_TOKENS`, with
    env override ``OPHAMIN_AGENT_MAXTOK_<TASK>``.
    """
    tier = TASK_ROUTING.get(task, TaskTier.WORKHORSE)
    env_model = os.environ.get(f"OPHAMIN_AGENT_MODEL_{task.upper()}", "").strip()
    model = env_model or DEFAULT_TIER_MODELS[tier]
    env_maxtok = os.environ.get(f"OPHAMIN_AGENT_MAXTOK_{task.upper()}", "")
    try:
        max_tokens = int(env_maxtok) if env_maxtok else DEFAULT_MAX_TOKENS.get(task, 2048)
    except ValueError:
        max_tokens = DEFAULT_MAX_TOKENS.get(task, 2048)
    return ModelChoice(tier=tier, model=model, max_tokens=max_tokens)
