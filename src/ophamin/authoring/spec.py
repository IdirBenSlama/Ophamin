"""ScenarioSpec — a grounded, declarative descriptor of an experiment.

This is the contract layer for *authoring* scenarios — by hand, from a file,
or (eventually) from a natural-language description handed to an offline
model. It exists to make one thing impossible: an ungrounded or synthetic
scenario slipping into the corpus.

The spec carries everything the Ophamin Protocol requires of a claim BEFORE
it runs:

  * a **falsifiable threshold** (metric / comparator / value) — no threshold,
    not falsifiable, not a scenario;
  * **scientific grounding** — at least one paper or recognised standard the
    claim rests on;
  * a **real data source** — a registered corpus or a substrate trajectory,
    never ``synthetic`` / ``inline`` / ``mock``;
  * **scope** (point | flow | campaign | vertical) and **facet** (neuro |
    physics | math | novel-cs | engineering) per the Protocol grid;
  * the **tools** selected for the task (from the capability manifest), and
    whether they were chosen by a human or auto-selected.

A spec is just data. :func:`ophamin.authoring.validation.validate_spec`
enforces the grounding gate; :mod:`ophamin.authoring.capabilities` lists what
a (human or model) author may select from.

**No LLM runs here.** A model may *fill* a spec offline (Ophamin tooling
layer), but the spec — and the scenario it materialises into — runs with no
LLM in the measurement path, per the substrate's no-external-LLM rule. The
authoring model is a tool that helps write the experiment, never a component
of the experiment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Protocol grid — kept here as the single source of truth for spec validation.
SCOPES: tuple[str, ...] = ("point", "flow", "campaign", "vertical")
FACETS: tuple[str, ...] = ("neuro", "physics", "math", "novel-cs", "engineering")
COMPARATORS: tuple[str, ...] = (">=", "<=", ">", "<", "==", "!=")
GROUNDING_KINDS: tuple[str, ...] = ("paper", "standard", "dataset-card", "benchmark")
#: Data-source kinds that are explicitly forbidden — the anti-synthetic gate.
FORBIDDEN_DATA_KINDS: frozenset[str] = frozenset(
    {"synthetic", "inline", "mock", "fabricated", "hardcoded", "stub"}
)
AUTHORED_BY: tuple[str, ...] = ("human", "model", "hybrid")


@dataclass(frozen=True)
class GroundingRef:
    """One scientific anchor for a claim — a paper, standard, or dataset card.

    ``ref`` is the locator (DOI, arXiv id, URL, or standard name); ``title``
    is the human label. ``kind`` is one of :data:`GROUNDING_KINDS`.
    """

    kind: str
    ref: str
    title: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "ref": self.ref, "title": self.title}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "GroundingRef":
        return cls(
            kind=str(d.get("kind", "")),
            ref=str(d.get("ref", "")),
            title=str(d.get("title", "")),
        )


@dataclass(frozen=True)
class Threshold:
    """The falsifiable decision boundary."""

    metric: str
    comparator: str
    value: float
    units: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "comparator": self.comparator,
            "value": self.value,
            "units": self.units,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Threshold":
        return cls(
            metric=str(d.get("metric", "")),
            comparator=str(d.get("comparator", "")),
            value=d.get("value"),  # type: ignore[arg-type]  # validated downstream; may be non-numeric
            units=str(d.get("units", "")),
        )


@dataclass(frozen=True)
class DataSourceRef:
    """Where the experiment's stimuli/records come from.

    ``kind`` describes the source class (e.g. ``corpus``,
    ``substrate-trajectory``). ``name`` identifies it (e.g. the corpus name
    ``enron``, or the substrate ``kimera-swm``). A ``kind`` in
    :data:`FORBIDDEN_DATA_KINDS` fails validation — the anti-synthetic gate.
    """

    kind: str
    name: str
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "name": self.name, "detail": dict(self.detail)}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DataSourceRef":
        return cls(
            kind=str(d.get("kind", "")),
            name=str(d.get("name", "")),
            detail=dict(d.get("detail", {}) or {}),
        )


@dataclass(frozen=True)
class ScenarioSpec:
    """A grounded, declarative experiment descriptor.

    Construct by hand, :meth:`from_dict` (file / API), or have an offline
    model fill it from a description. Validate with
    :func:`ophamin.authoring.validation.validate_spec` before materialising
    into a runnable scenario.
    """

    title: str
    scope: str
    facet: str
    claim_statement: str
    operationalization: str
    threshold: Threshold
    grounding: tuple[GroundingRef, ...]
    data_source: DataSourceRef
    invariant_template: str = ""        # e.g. "recognition" | "phi" | "" (custom)
    tools: tuple[str, ...] = ()
    authored_by: str = "human"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "scope": self.scope,
            "facet": self.facet,
            "claim_statement": self.claim_statement,
            "operationalization": self.operationalization,
            "threshold": self.threshold.to_dict(),
            "grounding": [g.to_dict() for g in self.grounding],
            "data_source": self.data_source.to_dict(),
            "invariant_template": self.invariant_template,
            "tools": list(self.tools),
            "authored_by": self.authored_by,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ScenarioSpec":
        return cls(
            title=str(d.get("title", "")),
            scope=str(d.get("scope", "")),
            facet=str(d.get("facet", "")),
            claim_statement=str(d.get("claim_statement", "")),
            operationalization=str(d.get("operationalization", "")),
            threshold=Threshold.from_dict(d.get("threshold", {}) or {}),
            grounding=tuple(
                GroundingRef.from_dict(g) for g in (d.get("grounding", []) or [])
            ),
            data_source=DataSourceRef.from_dict(d.get("data_source", {}) or {}),
            invariant_template=str(d.get("invariant_template", "")),
            tools=tuple(str(t) for t in (d.get("tools", []) or [])),
            authored_by=str(d.get("authored_by", "human")),
            notes=str(d.get("notes", "")),
        )
