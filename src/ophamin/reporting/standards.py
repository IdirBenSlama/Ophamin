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

  * **Standards coverage** — which recognised standards the proof satisfies.
    These are SUBSTANTIVE checks (CR7), not structural-presence: in-toto/DSSE
    (signature is a valid 64/128-hex digest, not just non-empty), W3C PROV-O
    (the graph actually has non-empty agent + activity + entity), OSF
    Registered Reports (prereg has the plan AND ``preregistered_at`` is
    strictly before ``created_at`` — the real anti-p-hacking lock), MLCommons
    Croissant (every dataset is a usable card: name + content_hash +
    n_records≥1 + source/kind), Stanford HELM (≥1 evidence pillar with
    substantive raw detail, not a single headline number), RO-Crate (the
    bundle has proof.json + a human render on disk — verifiable only when a
    ``bundle_dir`` is supplied).

``report_conformance`` returns a structured report: per-item results, the
standards satisfied vs missing, and ``conformant`` (True iff every required
nomenclature item passes — standards coverage is reported, never required,
since not every proof needs every standard).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ophamin.reporting.base import ReportFormat

# The Ophamin verdict vocabulary + comparators — the fixed nomenclature.
VERDICT_VOCABULARY: tuple[str, ...] = ("VALIDATED", "REFUTED", "INCONCLUSIVE")
COMPARATORS: tuple[str, ...] = (">=", "<=", ">", "<", "==", "!=")
_HASH_RE = re.compile(r"^[0-9a-f]{16,64}$")
_SNAKE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")
# A real attestation signature: HMAC-SHA256 (64 hex) or ed25519 (128 hex).
_SIG_RE = re.compile(r"^[0-9a-f]{64}([0-9a-f]{64})?$")
# RO-Crate bundle: the signed JSON plus at least one human-readable render.
_RO_CRATE_RENDERS: tuple[str, ...] = ("proof.md", "proof.html", "proof.pdf", "proof.tex")


def _isoparse(value: str) -> datetime | None:
    """Parse an ISO-8601 timestamp; None if it doesn't parse (no guessing)."""
    try:
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None

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
                   "a signature that is a valid 64- or 128-hex digest"),
    ReportStandard("w3c-prov-o", "provenance graph",
                   "a PROV-JSON graph with non-empty agent, activity AND entity"),
    ReportStandard("osf-registered-reports", "pre-registration of claim + plan",
                   "config_hash + analysis_plan AND preregistered_at strictly "
                   "before created_at (the anti-p-hacking lock)"),
    ReportStandard("mlcommons-croissant", "dataset cards",
                   "every dataset carries name + content_hash + n_records≥1 + "
                   "source/kind (a usable card, not just a hash)"),
    ReportStandard("stanford-helm", "raw transparency",
                   "≥1 evidence pillar with substantive detail (raw series/"
                   "structure, not a single headline number)"),
    ReportStandard("ro-crate", "research-object packaging",
                   "the bundle has proof.json + ≥1 human render (md/html/pdf/"
                   "tex) on disk — verifiable only with the bundle dir"),
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


def _detail_is_substantive(detail: Any) -> bool:
    """True iff an evidence detail is real raw transparency, not a headline.

    A single scalar key (e.g. ``{"n_pairs": 24}``) is a headline number, not
    HELM-style raw transparency. Substantive = ≥2 keys, OR a nested
    list/dict value (a series, distribution, control block, etc.).
    """
    if not isinstance(detail, dict) or not detail:
        return False
    if len(detail) >= 2:
        return True
    return any(isinstance(v, (list, dict)) and v for v in detail.values())


def _dataset_card_complete(d: dict[str, Any]) -> bool:
    """A usable Croissant card: name + content_hash + n_records≥1 + source/kind."""
    if not d.get("name") or not d.get("content_hash"):
        return False
    n = d.get("n_records")
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        return False
    return bool(d.get("source") or d.get("kind"))


def _provenance_is_prov_o(prov: Any) -> bool:
    """Real PROV-JSON: non-empty agent AND activity AND entity blocks."""
    if not isinstance(prov, dict):
        return False
    return all(bool(prov.get(k)) for k in ("agent", "activity", "entity"))


def _prereg_precedes_result(proof: dict[str, Any]) -> bool:
    """OSF anti-p-hacking lock: prereg has the plan AND preregistered_at is
    strictly before created_at (both must parse as real timestamps)."""
    prereg = proof.get("preregistration") or {}
    if not (prereg.get("config_hash") and prereg.get("analysis_plan")):
        return False
    pre = _isoparse(prereg.get("preregistered_at", ""))
    created = _isoparse(
        (proof.get("identity", {}) or {}).get("created_at", "")
        or proof.get("created_at", "")
    )
    return pre is not None and created is not None and pre < created


def _ro_crate_on_disk(bundle_dir: str | Path | None) -> bool | None:
    """True iff the bundle has proof.json + ≥1 human render on disk.

    Returns None when no bundle_dir is given — RO-Crate is a bundle-level
    property and is NOT verifiable from the record dict alone. None is honest:
    "not checked", distinct from False ("checked, missing").
    """
    if bundle_dir is None:
        return None
    d = Path(bundle_dir)
    if not (d / "proof.json").exists():
        return False
    return any((d / r).exists() for r in _RO_CRATE_RENDERS)


def _standards_items(
    proof: dict[str, Any], bundle_dir: str | Path | None = None,
) -> list[ConformanceItem]:
    """Substantive standards checks — each verifies the standard's real
    requirement, not mere block-presence (CR7)."""
    evidence = proof.get("evidence", []) or []
    datasets = (proof.get("data", {}) or {}).get("datasets") or proof.get("datasets", []) or []
    sig = str(proof.get("signature", ""))

    ro_crate = _ro_crate_on_disk(bundle_dir)
    # checks map id -> bool|None (None = not verifiable here, only for ro-crate)
    checks: dict[str, bool | None] = {
        "in-toto/DSSE": bool(_SIG_RE.match(sig)),
        "w3c-prov-o": _provenance_is_prov_o(proof.get("provenance")),
        "osf-registered-reports": _prereg_precedes_result(proof),
        "mlcommons-croissant": bool(datasets) and all(
            _dataset_card_complete(d) for d in datasets
        ),
        "stanford-helm": bool(evidence) and any(
            _detail_is_substantive(e.get("detail")) for e in evidence
        ),
        "ro-crate": ro_crate,
    }
    items: list[ConformanceItem] = []
    for std in REPORT_STANDARDS:
        ok = checks.get(std.id, False)
        if ok is None:
            detail = (
                f"{std.covers}: not verifiable from the record alone — pass "
                f"the bundle dir to check ({std.requires})."
            )
            fix = "Call report_conformance(proof, bundle_dir=…) to verify RO-Crate."
        else:
            detail = f"{std.covers}: {'satisfied' if ok else 'not satisfied'} ({std.requires})."
            fix = "" if ok else f"Satisfy: {std.requires}."
        items.append(ConformanceItem(
            "standard", std.id, bool(ok), WARN, detail, fix,
        ))
    return items


def report_conformance(
    proof: dict[str, Any], bundle_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Check a proof's nomenclature + standards coverage.

    Returns a structured report. ``conformant`` is True iff every required
    nomenclature item passes (standards coverage is reported, not required —
    not every proof needs every standard). The standards checks are
    SUBSTANTIVE, not structural-presence (CR7): each verifies the standard's
    real requirement (valid signature digest; PROV-O agent+activity+entity;
    prereg strictly before the result; complete dataset cards; raw evidence
    detail). ``bundle_dir`` enables the RO-Crate on-disk check (proof.json +
    a human render); without it RO-Crate is reported not-satisfied because it
    is a bundle-level property not verifiable from the record alone.
    """
    nomenclature = _nomenclature_items(proof)
    standards = _standards_items(proof, bundle_dir=bundle_dir)
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
