"""Tests for the zetetic directive — Ophamin's anti-sycophancy discipline.

Sycophancy can't be bought by model selection (the best models still cave
29–57% of the time, worse under pushback). So Ophamin enforces objectivity as
a DISCIPLINE: every agent's system prompt is prefixed with the zetetic
directive. These tests pin the directive's content and — critically — a
regression guard that the discipline cannot silently drop out of any one
agent.
"""

from __future__ import annotations

import pathlib

from ophamin.agentic.persona import ZETETIC_DIRECTIVE, zetetic_system

_AGENTS_DIR = pathlib.Path(__file__).resolve().parent.parent / "src" / "ophamin" / "agentic" / "agents"
_AGENT_FILES = [
    "adapter_gen", "bundle_query", "confound_enumerator", "prereg_validator",
    "proof_brief", "refuted_triage", "result_diagnosis", "scenario_gen",
]


# whitespace-collapsed directive so substring checks survive line-wrapping.
_D = " ".join(ZETETIC_DIRECTIVE.lower().split())


class TestDirective:
    def test_directive_forbids_sycophancy(self):
        assert "sycophancy is a defect" in _D
        assert "do not cave" in _D
        assert "instrument" in _D  # "you are an instrument, not an assistant"

    def test_directive_demands_objectivity_and_uncertainty(self):
        assert "objective" in _D
        assert "falsify" in _D            # state what would falsify it
        assert "if you do not know, say so" in _D

    def test_directive_bans_marketing_language(self):
        assert "no marketing language" in _D

    def test_directive_holds_line_under_pushback(self):
        # the specific failure mode the research flags (regressive sycophancy):
        # caving when challenged. The directive must address it directly.
        assert "agreement is earned by evidence" in _D

    def test_zetetic_system_prepends_directive(self):
        out = zetetic_system("ROLE PROMPT BODY")
        assert out.startswith(ZETETIC_DIRECTIVE)
        assert "ROLE PROMPT BODY" in out


class TestEveryAgentEnforcesIt:
    """Regression guard: the discipline must be wired into EVERY agent. If a
    new agent is added without zetetic_system, this fails — the anti-sycophancy
    promise can't quietly regress in one place."""

    def test_all_known_agents_wrap_system_prompt(self):
        missing = []
        for name in _AGENT_FILES:
            src = (_AGENTS_DIR / f"{name}.py").read_text(encoding="utf-8")
            if "zetetic_system(_SYSTEM_PROMPT)" not in src:
                missing.append(name)
        assert not missing, f"agents missing the zetetic discipline: {missing}"

    def test_no_agent_uses_bare_system_prompt(self):
        # catch the regression where someone reverts to the un-disciplined
        # {"role": "system", "content": _SYSTEM_PROMPT} form.
        offenders = []
        for name in _AGENT_FILES:
            src = (_AGENTS_DIR / f"{name}.py").read_text(encoding="utf-8")
            if '"content": _SYSTEM_PROMPT}' in src:
                offenders.append(name)
        assert not offenders, f"agents using bare (un-disciplined) prompt: {offenders}"

    def test_diagnosis_built_message_contains_directive(self):
        # behavioral check on the flagship analysis agent.
        from ophamin.agentic.agents.result_diagnosis import build_diagnosis_messages

        msgs = build_diagnosis_messages([{
            "proof_id": "x",
            "claim": {"statement": "s",
                      "threshold": {"metric": "m", "comparator": ">=", "value": 1}},
            "verdict": {"outcome": "VALIDATED", "observed_value": 1, "reasoning": "r"},
            "evidence": [],
        }])
        system = next(m["content"] for m in msgs if m["role"] == "system")
        assert "NON-NEGOTIABLE" in system
        assert "Sycophancy is a defect" in system
