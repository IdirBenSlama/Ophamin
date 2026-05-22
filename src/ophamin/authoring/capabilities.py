"""The capability manifest — what a (human or model) author may select from.

``available_capabilities()`` reports the real, registered resources an
experiment can be built on: the corpora that actually exist on this install,
the Protocol scopes + facets, the invariant templates that map to runnable
scenarios, the measurement tools/pillars, and the recognised scientific
standards. It is sourced from the live registries (corpus connectors,
scenario registry) — never a hand-maintained list that can drift.

This is the "auto + manual selective tools/toolkit" surface: a manual author
picks from it; an offline authoring model is handed it as the menu of real
options so it cannot invent a tool or dataset that does not exist.

No LLM is involved — this is a deterministic read of the registries.
"""

from __future__ import annotations

from typing import Any

from ophamin.authoring.spec import FACETS, GROUNDING_KINDS, SCOPES


#: Invariant templates that map a chosen invariant to a runnable scenario.
#: Each carries a grounding hint so an author knows what the claim rests on.
_INVARIANT_TEMPLATES: tuple[dict[str, Any], ...] = (
    {
        "name": "recognition",
        "scenario": "memory-deformation-flow",
        "scope": "flow",
        "facet": "neuro",
        "metric": "recognition_jaccard_floor",
        "comparator": ">=",
        "describes": (
            "memory-as-deformation: across re-exposures, the substrate keeps "
            "recognising a stimulus (concept-set Jaccard) even as the "
            "manifold deforms."
        ),
        "grounding_hint": "Kimera Session 013 / Round M recognition-floor record; IIT.",
    },
    {
        "name": "phi",
        "scenario": "phi-stability-flow",
        "scope": "flow",
        "facet": "neuro",
        "metric": "phi_floor",
        "comparator": ">=",
        "describes": (
            "cognitive non-collapse: under sustained load the substrate keeps "
            "Φ (integrated information) above a floor on real-input cycles."
        ),
        "grounding_hint": "Tononi IIT (Φ); Kimera Round M Φ-stability record.",
    },
    {
        "name": "manifold-topology",
        "scenario": "manifold-topology",
        "scope": "point",
        "facet": "math",
        "metric": "manifold_betti_0_median",
        "comparator": "==",
        "describes": (
            "manifold connectivity: the semantic manifold stays a single "
            "connected component (β₀ == 1) under exposure."
        ),
        "grounding_hint": "Persistent homology (Edelsbrunner-Harer); Betti numbers.",
    },
)

#: Measurement tools / pillars an experiment may draw on (the O·F·A·M·I·N
#: pillars, each backed by a mature library).
_TOOLS: tuple[dict[str, str], ...] = (
    {"id": "statsmodels", "pillar": "measuring", "use": "proportions, CIs, hypothesis tests"},
    {"id": "scikit-learn", "pillar": "measuring", "use": "clustering, classification metrics"},
    {"id": "mlflow", "pillar": "reporting", "use": "run + artifact tracking"},
    {"id": "dvc", "pillar": "seeing", "use": "dataset versioning"},
    {"id": "prov", "pillar": "comparing", "use": "W3C PROV provenance graphs"},
    {"id": "river", "pillar": "instrumenting", "use": "online/streaming metrics"},
    {"id": "mapie", "pillar": "auditing", "use": "conformal prediction intervals"},
)

#: Recognised scientific / industrial standards the Protocol is built on —
#: an author cites one of these (or a paper) to ground a claim.
_STANDARDS: tuple[dict[str, str], ...] = (
    {"id": "osf-registered-reports", "use": "pre-registration of claim + analysis plan"},
    {"id": "in-toto/SLSA", "use": "signed attestation envelope"},
    {"id": "stanford-helm", "use": "holistic eval + raw transparency"},
    {"id": "mlcommons-croissant", "use": "dataset cards"},
    {"id": "w3c-prov-o", "use": "provenance ontology"},
    {"id": "ro-crate", "use": "research object packaging"},
    {"id": "opentelemetry-semconv", "use": "telemetry semantic conventions"},
)


def available_capabilities() -> dict[str, Any]:
    """Return the live menu of real resources an author may select from."""
    # Corpora — read from the live connector registry; report availability.
    corpora: list[dict[str, Any]] = []
    try:
        from ophamin.seeing.corpus import available_corpora, list_corpus_names

        avail = available_corpora()
        for name in list_corpus_names():
            corpora.append({"name": name, "available": bool(avail.get(name, False))})
    except Exception:  # noqa: BLE001 — manifest is best-effort, never raises
        corpora = []

    # Scenarios — read from the live scenario registry.
    scenarios: list[dict[str, Any]] = []
    try:
        from ophamin.measuring.scenarios import SCENARIOS

        for name, sc in SCENARIOS.items():
            scenarios.append({
                "name": name,
                "tier": getattr(getattr(sc, "tier", None), "value", ""),
                "family": getattr(sc, "family", ""),
                "scope": getattr(sc, "scope", "point"),
            })
        scenarios.sort(key=lambda s: s["name"])
    except Exception:  # noqa: BLE001
        scenarios = []

    return {
        "scopes": list(SCOPES),
        "facets": list(FACETS),
        "grounding_kinds": list(GROUNDING_KINDS),
        "corpora": corpora,
        "scenarios": scenarios,
        "invariant_templates": [dict(t) for t in _INVARIANT_TEMPLATES],
        "tools": [dict(t) for t in _TOOLS],
        "standards": [dict(s) for s in _STANDARDS],
    }


def invariant_template_names() -> set[str]:
    return {t["name"] for t in _INVARIANT_TEMPLATES}


def tool_ids() -> set[str]:
    return {t["id"] for t in _TOOLS}
