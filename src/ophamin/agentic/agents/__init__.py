"""The four canonical agents.

Each agent is a single-function module:

- :func:`adapter_gen.generate` — natural-lang dataset description → adapter source
- :func:`proof_brief.write_brief` — proof.json → contextual proof.md
- :func:`refuted_triage.propose_followups` — REFUTED proof → 1-3 follow-up claims
- :func:`bundle_query.parse_query` — natural-lang → bundle_tree() filter spec

All four go through :class:`ophamin.agentic.LLMClient`, route via
:func:`ophamin.agentic.pick_model`, and persist their call as a
signed :class:`ophamin.agentic.LLMCallRecord` (unless ``audit=False``).
"""

from ophamin.agentic.agents.adapter_gen import generate as adapter_gen
from ophamin.agentic.agents.proof_brief import write_brief
from ophamin.agentic.agents.refuted_triage import propose_followups
from ophamin.agentic.agents.bundle_query import parse_query
from ophamin.agentic.agents.result_diagnosis import diagnose

__all__ = [
    "adapter_gen",
    "write_brief",
    "propose_followups",
    "parse_query",
    "diagnose",
]
