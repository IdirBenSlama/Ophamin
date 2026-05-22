"""The grounding gate — validate_spec().

This is the load-bearing piece of the authoring layer: it makes an
ungrounded or synthetic :class:`ScenarioSpec` fail *before* it can become a
scenario, no matter who wrote it (a person, a file, or an offline model).

A spec is **acceptable** only when every Protocol requirement is met:

  * a falsifiable threshold (metric + valid comparator + numeric value);
  * at least one scientific grounding ref (paper / standard / dataset card);
  * a real data source — a registered corpus, or a substrate trajectory —
    never synthetic / inline / mock;
  * a valid scope and facet;
  * an invariant template that exists (if one is named);
  * tools that exist in the capability manifest (if any are named);
  * non-empty claim + operationalization.

Violations are returned as structured records (never raised) so a Console or
an authoring model gets an actionable punch list: which field, what's wrong,
and how to fix it. ``is_acceptable`` is True iff there are no ERROR-severity
violations (WARN-severity items are advisory).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ophamin.authoring.capabilities import (
    available_capabilities,
    invariant_template_names,
    tool_ids,
)
from ophamin.authoring.spec import (
    COMPARATORS,
    FACETS,
    FORBIDDEN_DATA_KINDS,
    GROUNDING_KINDS,
    SCOPES,
    ScenarioSpec,
)

ERROR = "error"
WARN = "warn"


@dataclass(frozen=True)
class SpecViolation:
    """One thing wrong with a spec — actionable, structured."""

    field: str
    code: str
    severity: str
    message: str
    fix: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "fix": self.fix,
        }


def validate_spec(spec: ScenarioSpec) -> list[SpecViolation]:
    """Return all violations of the grounding gate (empty list = clean)."""
    v: list[SpecViolation] = []

    # --- claim must be stated -------------------------------------------------
    if not spec.title.strip():
        v.append(SpecViolation("title", "missing_title", ERROR,
                               "Spec has no title.", "Give the experiment a title."))
    if not spec.claim_statement.strip():
        v.append(SpecViolation("claim_statement", "missing_claim", ERROR,
                               "No claim statement — there is nothing to test.",
                               "State the falsifiable claim in one sentence."))
    if not spec.operationalization.strip():
        v.append(SpecViolation("operationalization", "missing_operationalization", ERROR,
                               "No operationalization — the claim isn't measurable.",
                               "Describe exactly how the metric is computed."))

    # --- falsifiable threshold (the Protocol's hard requirement) -------------
    t = spec.threshold
    if not t.metric.strip():
        v.append(SpecViolation("threshold.metric", "missing_metric", ERROR,
                               "No metric — claim is not falsifiable.",
                               "Name the measured quantity."))
    if t.comparator not in COMPARATORS:
        v.append(SpecViolation("threshold.comparator", "bad_comparator", ERROR,
                               f"Comparator {t.comparator!r} not in {list(COMPARATORS)}.",
                               "Use one of >=, <=, >, <, ==, !=."))
    if not isinstance(t.value, (int, float)) or isinstance(t.value, bool):
        v.append(SpecViolation("threshold.value", "non_numeric_threshold", ERROR,
                               f"Threshold value {t.value!r} is not numeric — not falsifiable.",
                               "Give a numeric decision boundary."))

    # --- scientific grounding (no synthetic, no ungrounded) ------------------
    if not spec.grounding:
        v.append(SpecViolation("grounding", "missing_grounding", ERROR,
                               "No scientific grounding — claim rests on nothing.",
                               "Cite >=1 paper, standard, or dataset card."))
    for i, g in enumerate(spec.grounding):
        if g.kind not in GROUNDING_KINDS:
            v.append(SpecViolation(f"grounding[{i}].kind", "bad_grounding_kind", ERROR,
                                   f"Grounding kind {g.kind!r} not in {list(GROUNDING_KINDS)}.",
                                   "Use paper / standard / dataset-card / benchmark."))
        if not g.ref.strip():
            v.append(SpecViolation(f"grounding[{i}].ref", "empty_grounding_ref", ERROR,
                                   "Grounding has no locator (DOI / arXiv / URL / name).",
                                   "Provide the reference locator."))

    # --- real data source (the anti-synthetic gate) --------------------------
    ds = spec.data_source
    caps = available_capabilities()
    corpus_names = {c["name"] for c in caps.get("corpora", [])}
    available_corpus_names = {c["name"] for c in caps.get("corpora", []) if c.get("available")}
    if not ds.kind.strip():
        v.append(SpecViolation("data_source.kind", "missing_data_kind", ERROR,
                               "No data source kind.",
                               "Use corpus or substrate-trajectory."))
    elif ds.kind.lower() in FORBIDDEN_DATA_KINDS:
        v.append(SpecViolation("data_source.kind", "synthetic_data_forbidden", ERROR,
                               f"Data source {ds.kind!r} is synthetic/fabricated — forbidden.",
                               "Use a real registered corpus or a substrate trajectory."))
    elif ds.kind == "corpus":
        if ds.name not in corpus_names:
            v.append(SpecViolation("data_source.name", "unknown_corpus", ERROR,
                                   f"Corpus {ds.name!r} is not registered. "
                                   f"Known: {sorted(corpus_names)}.",
                                   "Pick a registered corpus from the capability manifest."))
        elif ds.name not in available_corpus_names:
            v.append(SpecViolation("data_source.name", "corpus_unavailable", WARN,
                                   f"Corpus {ds.name!r} is registered but not available "
                                   "on this install.",
                                   "Provision the corpus, or pick an available one."))

    # --- scope / facet (Protocol grid) ---------------------------------------
    if spec.scope not in SCOPES:
        v.append(SpecViolation("scope", "bad_scope", ERROR,
                               f"Scope {spec.scope!r} not in {list(SCOPES)}.",
                               "Use point / flow / campaign / vertical."))
    if spec.facet not in FACETS:
        v.append(SpecViolation("facet", "bad_facet", ERROR,
                               f"Facet {spec.facet!r} not in {list(FACETS)}.",
                               "Use neuro / physics / math / novel-cs / engineering."))

    # --- invariant template + tools must exist (no inventing) ----------------
    if spec.invariant_template:
        if spec.invariant_template not in invariant_template_names():
            v.append(SpecViolation("invariant_template", "unknown_template", ERROR,
                                   f"Invariant template {spec.invariant_template!r} does not exist. "
                                   f"Known: {sorted(invariant_template_names())}.",
                                   "Pick a template from the manifest, or leave blank for custom."))
    known_tools = tool_ids()
    for tool in spec.tools:
        if tool not in known_tools:
            v.append(SpecViolation("tools", "unknown_tool", ERROR,
                                   f"Tool {tool!r} is not in the capability manifest. "
                                   f"Known: {sorted(known_tools)}.",
                                   "Select a real tool, or remove it."))

    # --- authored_by provenance ----------------------------------------------
    if spec.authored_by not in ("human", "model", "hybrid"):
        v.append(SpecViolation("authored_by", "bad_authored_by", WARN,
                               f"authored_by {spec.authored_by!r} unrecognised.",
                               "Use human / model / hybrid for the audit trail."))

    return v


def is_acceptable(violations: list[SpecViolation]) -> bool:
    """True iff no ERROR-severity violations (WARN items are advisory)."""
    return not any(x.severity == ERROR for x in violations)


def validate_spec_dict(d: dict[str, Any]) -> dict[str, Any]:
    """Validate a spec given as a plain dict (file / API path).

    Returns a structured result: ``acceptable`` + the violation list +
    the normalised spec echo. Never raises on a malformed dict — a parse
    problem surfaces as an ERROR violation.
    """
    try:
        spec = ScenarioSpec.from_dict(d)
    except Exception as exc:  # noqa: BLE001 — malformed input is a finding, not a crash
        return {
            "acceptable": False,
            "violations": [SpecViolation(
                "(root)", "unparseable_spec", ERROR,
                f"Spec could not be parsed: {type(exc).__name__}: {exc}",
                "Fix the spec structure (see ScenarioSpec fields).",
            ).to_dict()],
            "spec": None,
        }
    violations = validate_spec(spec)
    return {
        "acceptable": is_acceptable(violations),
        "violations": [x.to_dict() for x in violations],
        "spec": spec.to_dict(),
    }
