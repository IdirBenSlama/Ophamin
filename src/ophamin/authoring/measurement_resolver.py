"""Measurement resolver — how Ophamin provides a measurement it doesn't have.

When an experiment reveals a measurement requirement that is not yet present
(e.g. the memory-horizon proof surfacing the need for a *partial-cue* recall
metric to separate memory from deterministic re-derivation), Ophamin does NOT
go invent a number. It routes the requirement across three real lists and
returns a recipe:

  1. **Compose** — the capability menu (`authoring.capabilities`): invariant
     templates that already map to runnable scenarios, plus the O·F·A·M·I·N
     pillars/tools. Most "new" measurements are a *composition* of these (a
     new scenario), not a new tool.
  2. **Wire** — the toolkit registry (`interop.toolkit_registry`): mature
     external tools available to bring in as a new pillar when composition
     alone can't reach the requirement.
  3. **Synthesize** — only when neither composes nor wires: the `scenario_gen`
     agent generates a new measurement primitive. This is the last resort.

Across all three, the **grounding gate is the guardrail**: a composed,
wired, or synthesized measurement must cite a resolvable paper/standard
(`authoring.grounding`). An invented, ungrounded measurement is refused by
construction — which is exactly what keeps a self-extending observatory
credible instead of a source of made-up metrics.

This module assembles the candidate lists + a heuristic recommended route. The
final selection is made by an agent (under the zetetic directive) and then
locked by the grounding gate — the resolver is the *list*, not the verdict.
"""

from __future__ import annotations

import re
from typing import Any

# resolution paths
COMPOSE_TEMPLATE = "compose-from-template"   # an existing scenario already fits
COMPOSE_PRIMITIVES = "compose-from-primitives"  # build a new scenario from pillars
WIRE_TOOLKIT = "wire-external-toolkit"       # bring in an external tool as a pillar
SYNTHESIZE = "synthesize-grounded-primitive"  # scenario_gen writes a new primitive

_STOP = frozenset({
    "the", "a", "an", "of", "to", "and", "or", "for", "in", "on", "is", "it",
    "that", "this", "with", "as", "by", "be", "we", "need", "measure",
    "measuring", "measurement", "tool", "whether", "from", "not", "yet",
    "present", "specific", "requirement", "substrate", "kimera", "ophamin",
})


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower())
            if len(w) > 2 and w not in _STOP}


def _overlap(need: set[str], target: str) -> float:
    """Jaccard-ish overlap of need tokens against a target string's tokens."""
    tt = _tokens(target)
    if not tt or not need:
        return 0.0
    return len(need & tt) / len(need)


def resolve_measurement(
    need: str, *, top_k: int = 3, match_floor: float = 0.18,
) -> dict[str, Any]:
    """Route a stated measurement requirement across the three lists.

    Returns ranked compose/wire candidates, a heuristic recommended ``path``,
    and the grounding requirement. Deterministic + side-effect-free: it reads
    the live capability menu + toolkit registry and scores by token overlap.
    The recommendation is a FIRST PASS — an agent makes the real selection and
    the grounding gate enforces it.
    """
    if not need or not need.strip():
        raise ValueError("measurement need must be a non-empty description")
    nt = _tokens(need)

    from ophamin.authoring.capabilities import (
        _INVARIANT_TEMPLATES,
        _STANDARDS,
        _TOOLS,
    )
    from ophamin.interop.toolkit_registry import toolkit_registry

    # 1. compose-from-template candidates. Track name/metric overlap
    #: separately from description overlap: a strong "this is already measured"
    #: claim must rest on the template's NAME or METRIC matching, not on
    #: ambient description words (otherwise "sustained load" spuriously matches
    #: the phi template for a GPU question).
    templates = []
    for t in _INVARIANT_TEMPLATES:
        score = _overlap(nt, f"{t['name']} {t['metric']} {t['describes']}")
        identity_overlap = _overlap(nt, f"{t['name']} {t['metric']}")
        templates.append({
            "name": t["name"], "scenario": t["scenario"], "metric": t["metric"],
            "describes": t["describes"], "grounding_hint": t.get("grounding_hint", ""),
            "score": round(score, 3), "identity_overlap": round(identity_overlap, 3),
        })
    templates.sort(key=lambda x: x["score"], reverse=True)

    # 2. compose-from-primitives candidates (the pillars)
    pillars = []
    for p in _TOOLS:
        score = _overlap(nt, f"{p['id']} {p['pillar']} {p['use']}")
        pillars.append({**p, "score": round(score, 3)})
    pillars.sort(key=lambda x: x["score"], reverse=True)

    # 3. wire-external-toolkit candidates (the registry)
    reg = toolkit_registry()
    toolkits = []
    for tk in reg["toolkits"]:
        score = _overlap(nt, f"{tk['id']} {tk['category']} {tk['role']}")
        toolkits.append({
            "id": tk["id"], "category": tk["category"], "role": tk["role"],
            "installed": tk["installed"], "docs_url": tk["docs_url"],
            "score": round(score, 3),
        })
    toolkits.sort(key=lambda x: x["score"], reverse=True)

    best_template = templates[0]["score"] if templates else 0.0
    best_pillar = pillars[0]["score"] if pillars else 0.0
    best_toolkit = toolkits[0]["score"] if toolkits else 0.0

    best_identity = templates[0]["identity_overlap"] if templates else 0.0

    # Heuristic route: claim "already measured" ONLY when the template's
    # name/metric actually overlaps (identity match), not on ambient words.
    # Otherwise compose a NEW scenario from primitives (the common case); or
    # wire a toolkit on a strong external-only fit; else synthesize.
    if best_template >= 0.5 and best_identity >= 0.2:
        path = COMPOSE_TEMPLATE
        rationale = (
            f"an existing scenario ({templates[0]['scenario']}) already measures "
            "this — configure/extend it rather than build new."
        )
    elif best_pillar >= match_floor or best_template >= match_floor:
        path = COMPOSE_PRIMITIVES
        rationale = (
            "no single existing scenario fits, but the requirement composes "
            "from existing pillars + a related template — author a new scenario "
            "(materializer builds it). Most missing measurements land here."
        )
    elif best_toolkit >= match_floor:
        path = WIRE_TOOLKIT
        rationale = (
            f"an external toolkit ({toolkits[0]['id']}) covers this — wire it in "
            "as a new pillar."
        )
    else:
        path = SYNTHESIZE
        rationale = (
            "nothing on the lists fits — scenario_gen synthesizes a new "
            "measurement primitive. Last resort; still grounded + tested."
        )

    return {
        "need": need,
        "path": path,
        "rationale": rationale,
        "compose_templates": templates[:top_k],
        "compose_pillars": pillars[:top_k],
        "wire_toolkits": toolkits[:top_k],
        "grounding_required": True,
        "grounding_note": (
            "Whatever the path, the chosen measurement MUST cite a resolvable "
            "paper or recognised standard — the grounding gate refuses an "
            "invented, ungrounded metric. The agent selects + cites; the gate "
            "enforces."
        ),
        "recognised_standards": [dict(s) for s in _STANDARDS],
        "scores": {
            "best_template": best_template,
            "best_pillar": best_pillar,
            "best_toolkit": best_toolkit,
        },
    }
