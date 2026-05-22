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
from typing import Any


class TaskTier(str, enum.Enum):
    """The model-class tiers.

    The first four are *general* classes (speed/quality trade-offs). The
    last two are **dedicated domain tiers** — for validating experiments
    with a model specialised for the domain, not a general one (per the
    owner's directive: scientific/engineering work wants dedicated models).
    """

    FAST = "fast"
    WORKHORSE = "workhorse"
    CODER = "coder"
    REASONING = "reasoning"
    SCIENTIFIC = "scientific"      # dedicated: claim/result scientific validation
    ENGINEERING = "engineering"    # dedicated: engineering diagnosis / cost review


class Provider(str, enum.Enum):
    """Where a tier's model runs.

    LOCAL is the default — the owner works with local models (Ollama /
    MLX-LM). EXTERNAL_API is opt-in per tier: point a tier at an
    OpenAI-compatible API with its own base URL and a key read from an
    env var (the key itself is never stored in config or proofs).
    """

    LOCAL = "local"
    EXTERNAL_API = "external_api"


@dataclass(frozen=True)
class ModelChoice:
    """One task's routed model: tier + concrete model tag + max-tokens hint,
    plus where it runs (provider + base_url + the env var holding the key).

    For LOCAL, ``base_url`` is the local runtime; ``api_key_env`` is unused
    (local runtimes ignore the token). For EXTERNAL_API, ``base_url`` is the
    API endpoint and ``api_key_env`` names the environment variable the
    caller reads the key from — the key is NEVER embedded here.
    """

    tier: TaskTier
    model: str
    max_tokens: int = 2048
    provider: Provider = Provider.LOCAL
    base_url: str = ""
    api_key_env: str = ""


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
    # Dedicated domain tiers. Defaults are sensible local models; the
    # operator points these at a science/engineering-tuned model (local or
    # external API) via the env vars below. Examples of dedicated models an
    # operator might wire: a chemistry/biology-tuned LLM, a code+math
    # reasoning model, or an external scientific-API model.
    TaskTier.SCIENTIFIC: os.environ.get(
        "OPHAMIN_LLM_MODEL_SCIENTIFIC", "deepseek-r1:32b",
    ),
    TaskTier.ENGINEERING: os.environ.get(
        "OPHAMIN_LLM_MODEL_ENGINEERING", "qwen2.5-coder:32b",
    ),
}


def _tier_provider(tier: TaskTier) -> tuple[Provider, str, str]:
    """Resolve (provider, base_url, api_key_env) for a tier from env.

    Local-first: every tier defaults to LOCAL with an empty base_url
    (the caller falls back to the framework-wide local default). A tier is
    switched to an external API only when the operator explicitly sets
    ``OPHAMIN_LLM_PROVIDER_<TIER>=external_api`` AND provides
    ``OPHAMIN_LLM_BASE_URL_<TIER>`` + ``OPHAMIN_LLM_API_KEY_ENV_<TIER>``
    (the *name* of the env var holding the key — never the key itself).
    """
    up = tier.value.upper()
    raw = os.environ.get(f"OPHAMIN_LLM_PROVIDER_{up}", "local").strip().lower()
    provider = Provider.EXTERNAL_API if raw == "external_api" else Provider.LOCAL
    base_url = os.environ.get(f"OPHAMIN_LLM_BASE_URL_{up}", "").strip()
    api_key_env = os.environ.get(f"OPHAMIN_LLM_API_KEY_ENV_{up}", "").strip()
    return provider, base_url, api_key_env


#: Per-task tier assignment. Edit here when adding new agents.
#:
#: Rationale:
#: - adapter_gen          → CODER     (code generation; quality > speed)
#: - proof_brief          → WORKHORSE (general English summarization)
#: - refuted_triage       → REASONING (hypothesis derivation needs CoT)
#: - bundle_query         → FAST      (NL → JSON filter; small + fast)
#: - prereg_validator     → REASONING (semantic falsifiability checks;
#:                                     0.63.2)
#: - confound_enumerator  → REASONING (red-team alternative explanations;
#:                                     0.63.2)
TASK_ROUTING: dict[str, TaskTier] = {
    "adapter_gen": TaskTier.CODER,
    "proof_brief": TaskTier.WORKHORSE,
    "refuted_triage": TaskTier.REASONING,
    "bundle_query": TaskTier.FAST,
    "prereg_validator": TaskTier.REASONING,
    "confound_enumerator": TaskTier.REASONING,
    # 0.63.3 — scaffolds a Scenario subclass from a claim. Same tier
    # as adapter_gen for the same reason: code generation rewards
    # quality over speed.
    "scenario_gen": TaskTier.CODER,
    # 0.85.0 — dedicated-domain validation/diagnosis tasks. These route to
    # the SCIENTIFIC / ENGINEERING tiers so a domain-dedicated model (not a
    # general one) performs the analysis the owner asked the agentic system
    # to do.
    "scientific_validation": TaskTier.SCIENTIFIC,   # validate a claim's science
    "result_diagnosis": TaskTier.SCIENTIFIC,        # diagnose a proof/result
    "engineering_diagnosis": TaskTier.ENGINEERING,  # cost/throughput diagnosis
    "report_synthesis": TaskTier.WORKHORSE,         # standards-conforming write-up
}


#: Per-task max-tokens budget. Override via env
#: ``OPHAMIN_AGENT_MAXTOK_<TASK>`` if a particular task needs longer output.
DEFAULT_MAX_TOKENS: dict[str, int] = {
    "adapter_gen": 4096,           # generated code can be long
    "proof_brief": 2048,
    "refuted_triage": 4096,        # reasoning chains can be long
    "bundle_query": 512,           # JSON filter is small
    "prereg_validator": 2048,      # structured JSON, modest size
    "confound_enumerator": 8192,   # 3-5 confounds × mechanism + test
    "scenario_gen": 6144,          # full Scenario subclass; docstring +
                                   # __init__ + build_claim() + score() stub
    # Reasoning-tier tasks need headroom: a reasoning model (DeepSeek-R1,
    # Qwen3.5, GPT-OSS-high) spends thousands of tokens in its reasoning
    # channel BEFORE the answer, and runtimes count that against max_tokens.
    # 4096 left no room for the structured answer after the thinking, so the
    # JSON came back truncated/empty. 8192 fits thinking + the answer.
    "scientific_validation": 8192,
    "result_diagnosis": 8192,
    "engineering_diagnosis": 8192,
    "refuted_triage": 8192,
    "report_synthesis": 8192,
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
    provider, base_url, api_key_env = _tier_provider(tier)
    return ModelChoice(
        tier=tier, model=model, max_tokens=max_tokens,
        provider=provider, base_url=base_url, api_key_env=api_key_env,
    )


def model_capabilities() -> dict[str, Any]:
    """Report the configured model routing — for the /models capability surface.

    Deterministic read of the env-resolved routing: every tier (general +
    dedicated), its current model + provider (local / external_api) + base
    URL + key-env-var name, and the per-task → tier map. Never includes a
    secret — only the *name* of the env var a key would be read from.
    """
    tiers: list[dict[str, Any]] = []
    for tier in TaskTier:
        provider, base_url, api_key_env = _tier_provider(tier)
        tiers.append({
            "tier": tier.value,
            "model": DEFAULT_TIER_MODELS[tier],
            "provider": provider.value,
            "base_url": base_url,
            "api_key_env": api_key_env,
            "dedicated": tier in (TaskTier.SCIENTIFIC, TaskTier.ENGINEERING),
        })
    tasks = [
        {"task": t, "tier": tier.value, "max_tokens": DEFAULT_MAX_TOKENS.get(t, 2048)}
        for t, tier in sorted(TASK_ROUTING.items())
    ]
    return {
        "tiers": tiers,
        "tasks": tasks,
        "default_provider": Provider.LOCAL.value,
        "external_api_enabled": any(
            t["provider"] == Provider.EXTERNAL_API.value for t in tiers
        ),
        "boundary": (
            "Tooling layer only — these models perform analysis / diagnosis "
            "/ authoring. No model is invoked from the measurement path "
            "(scenario.run); per the substrate's no-external-LLM rule."
        ),
    }
