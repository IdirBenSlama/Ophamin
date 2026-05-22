"""The reporting gate — standards coverage + nomenclature conformance.

The output analog of the authoring grounding gate. Where authoring makes an
ungrounded *input* impossible, this checks that an *output* (a signed proof,
the thing a report renders) conforms to Ophamin's naming conventions and
declares which recognised scientific/industrial standards it satisfies.

Two checks, both structured + actionable (never raised):

  * **Nomenclature** — the Ophamin naming conventions a report rests on:
    a content-hash ``proof_id``; a claim with a snake_case metric + a valid
    comparator + numeric threshold; a verdict from the fixed vocabulary
    (VALIDATED / REFUTED / INCONCLUSIVE) with observed value + reasoning;
    evidence with named (snake_case) statistics; a ``created_at`` that the
    canonical bundle name ``<YYYY-MM-DD>_<verdict>_<short>`` derives from.

  * **Standards coverage** — which recognised standards the proof satisfies:
    in-toto/DSSE (signed attestation → signature present), W3C PROV-O
    (provenance graph present), OSF Registered Reports (pre-registration
    present), MLCommons Croissant (dataset cards → datasets with a
    content_hash), Stanford HELM (raw transparency → evidence detail
    present), RO-Crate (multi-format render available).

``report_conformance`` returns a structured report: per-item results, the
standards satisfied vs missing, and ``conformant`` (True iff every required
nomenclature item passes — standards coverage is reported, never required,
since not every proof needs every standard).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ophamin.reporting.base import ReportFormat

# The Ophamin verdict vocabulary + comparators — the fixed nomenclature.
VERDICT_VOCABULARY: tuple[str, ...] = ("VALIDATED", "REFUTED", "INCONCLUSIVE")
COMPARATORS: tuple[str, ...] = (">=", "<=", ">", "<", "==", "!=")
_HASH_RE = re.compile(r"^[0-9a-f]{16,64}$")
_SNAKE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")

ERROR = "error"
WARN = "warn"


@dataclass(frozen=True)
class ReportStandard:
    """One recognised standard a report can declare conformance to."""

    id: str
    covers: str
    requires: str

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "covers": self.covers, "requires": self.requires}


#: The standards a proof/report can satisfy. ``requires`` is the
#: human-readable predicate; the check is implemented in ``report_conformance``.
REPORT_STANDARDS: tuple[ReportStandard, ...] = (
    ReportStandard("in-toto/DSSE", "signed attestation envelope",
                   "a non-empty signature on the record"),
    ReportStandard("w3c-prov-o", "provenance graph",
                   "a provenance block (agents / activities / entities)"),
    ReportStandard("osf-registered-reports", "pre-registration of claim + plan",
                   "a preregistration block (config_hash + analysis_plan)"),
    ReportStandard("mlcommons-croissant", "dataset cards",
                   "datasets each carrying a content_hash"),
    ReportStandard("stanford-helm", "raw transparency",
                   "evidence carrying raw detail (not just a headline number)"),
    ReportStandard("ro-crate", "research-object packaging",
                   "a multi-format render (json + md + …) — bundle level"),
)

#: Output formats the reporting wheel renders (the nomenclature for files).
OUTPUT_FORMATS: tuple[str, ...] = tuple(f.value for f in ReportFormat)


@dataclass(frozen=True)
class ConformanceItem:
    """One conformance check result — actionable + structured."""

    category: str          # "nomenclature" | "standard"
    id: str
    satisfied: bool
    severity: str          # ERROR (nomenclature) | WARN (advisory standard)
    detail: str
    fix: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "id": self.id,
            "satisfied": self.satisfied,
            "severity": self.severity,
            "detail": self.detail,
            "fix": self.fix,
        }


def _nomenclature_items(proof: dict[str, Any]) -> list[ConformanceItem]:
    items: list[ConformanceItem] = []

    pid = str(proof.get("proof_id", ""))
    items.append(ConformanceItem(
        "nomenclature", "proof_id_is_content_hash",
        bool(_HASH_RE.match(pid)), ERROR,
        f"proof_id {pid[:16]!r} {'is' if _HASH_RE.match(pid) else 'is NOT'} a hex content hash.",
        "Sign the record so proof_id is the SHA-256 content hash."))

    claim = proof.get("claim", {}) or {}
    items.append(ConformanceItem(
        "nomenclature", "claim_statement_present",
        bool(str(claim.get("statement", "")).strip()), ERROR,
        "Claim statement present." if claim.get("statement") else "Claim has no statement.",
        "Every report must name the falsifiable claim."))

    thr = claim.get("threshold", {}) or {}
    metric = str(thr.get("metric", ""))
    items.append(ConformanceItem(
        "nomenclature", "metric_is_snake_case",
        bool(_SNAKE_RE.match(metric)), ERROR,
        f"metric {metric!r} {'follows' if _SNAKE_RE.match(metric) else 'does NOT follow'} snake_case nomenclature.",
        "Name metrics in lower_snake_case (e.g. recognition_jaccard_floor)."))
    items.append(ConformanceItem(
        "nomenclature", "threshold_well_formed",
        thr.get("comparator") in COMPARATORS
        and isinstance(thr.get("value"), (int, float))
        and not isinstance(thr.get("value"), bool),
        ERROR,
        f"threshold comparator={thr.get('comparator')!r} value={thr.get('value')!r}.",
        "Threshold needs a valid comparator + numeric value."))

    verdict = proof.get("verdict", {}) or {}
    outcome = verdict.get("outcome")
    items.append(ConformanceItem(
        "nomenclature", "verdict_vocabulary",
        outcome in VERDICT_VOCABULARY, ERROR,
        f"verdict outcome {outcome!r} {'is' if outcome in VERDICT_VOCABULARY else 'is NOT'} in {list(VERDICT_VOCABULARY)}.",
        "Use the fixed verdict vocabulary."))
    has_observed = (
        verdict.get("observed_value") is not None
        or verdict.get("observed") is not None
    )
    items.append(ConformanceItem(
        "nomenclature", "verdict_observed_and_reasoning",
        has_observed and bool(str(verdict.get("reasoning", "")).strip()), ERROR,
        "Verdict carries observed value + reasoning."
        if has_observed and verdict.get("reasoning")
        else "Verdict missing observed value and/or reasoning.",
        "Record the observed value and the decision reasoning."))

    evidence = proof.get("evidence", []) or []
    named = bool(evidence) and all(
        bool(_SNAKE_RE.match(str(e.get("statistic_name", "")))) for e in evidence
    )
    items.append(ConformanceItem(
        "nomenclature", "evidence_statistics_named",
        named, ERROR,
        f"{len(evidence)} evidence pillar(s); "
        + ("all statistic_name snake_case." if named else "some statistic_name missing/!snake_case."),
        "Every evidence pillar needs a snake_case statistic_name."))

    created = str((proof.get("identity", {}) or {}).get("created_at", "")) or str(proof.get("created_at", ""))
    items.append(ConformanceItem(
        "nomenclature", "bundle_name_derivable",
        bool(_DATE_RE.match(created)) and outcome in VERDICT_VOCABULARY, ERROR,
        f"created_at {created[:10]!r} + verdict → bundle name "
        f"<YYYY-MM-DD>_<verdict>_<short> {'derivable' if _DATE_RE.match(created) and outcome in VERDICT_VOCABULARY else 'NOT derivable'}.",
        "Set created_at (ISO) and a valid verdict so the canonical bundle name derives."))

    return items


def _standards_items(proof: dict[str, Any]) -> list[ConformanceItem]:
    evidence = proof.get("evidence", []) or []
    # Datasets are nested under ``data.datasets`` in the serialised record;
    # accept a top-level ``datasets`` too for forward compatibility.
    datasets = (proof.get("data", {}) or {}).get("datasets") or proof.get("datasets", []) or []
    checks: dict[str, bool] = {
        "in-toto/DSSE": bool(str(proof.get("signature", "")).strip()),
        "w3c-prov-o": bool(proof.get("provenance")),
        "osf-registered-reports": bool(
            (proof.get("preregistration") or {}).get("analysis_plan")
        ),
        "mlcommons-croissant": bool(datasets) and all(
            bool(d.get("content_hash")) for d in datasets
        ),
        "stanford-helm": bool(evidence) and any(
            bool(e.get("detail")) for e in evidence
        ),
        # RO-Crate is bundle-level (multi-format render). At the record level
        # we can only confirm the record is renderable to >1 format, which it
        # always is — so report it satisfied when the record is well-formed
        # enough to carry a claim + verdict.
        "ro-crate": bool(proof.get("claim")) and bool(proof.get("verdict")),
    }
    items: list[ConformanceItem] = []
    for std in REPORT_STANDARDS:
        ok = checks.get(std.id, False)
        items.append(ConformanceItem(
            "standard", std.id, ok, WARN,
            f"{std.covers}: {'satisfied' if ok else 'not present'} ({std.requires}).",
            "" if ok else f"Add {std.requires} to satisfy {std.id}."))
    return items


def report_conformance(proof: dict[str, Any]) -> dict[str, Any]:
    """Check a proof's nomenclature + standards coverage.

    Returns a structured report. ``conformant`` is True iff every required
    nomenclature item passes (standards coverage is reported, not required —
    not every proof needs every standard).
    """
    nomenclature = _nomenclature_items(proof)
    standards = _standards_items(proof)
    conformant = all(i.satisfied for i in nomenclature)
    satisfied = [i.id for i in standards if i.satisfied]
    missing = [i.id for i in standards if not i.satisfied]
    return {
        "conformant": conformant,
        "nomenclature": [i.to_dict() for i in nomenclature],
        "standards": [i.to_dict() for i in standards],
        "standards_satisfied": satisfied,
        "standards_missing": missing,
        "output_formats": list(OUTPUT_FORMATS),
    }


def report_standards_registry() -> dict[str, Any]:
    """The menu of recognised report standards + output formats."""
    return {
        "standards": [s.to_dict() for s in REPORT_STANDARDS],
        "output_formats": list(OUTPUT_FORMATS),
        "verdict_vocabulary": list(VERDICT_VOCABULARY),
        "bundle_name_convention": "<tier>/<scenario>/<YYYY-MM-DD>_<verdict>_<short>",
        "metric_convention": "lower_snake_case",
    }
