"""SARIF 2.1.0 exporter — AuditRecord → SARIF.

SARIF (Static Analysis Results Interchange Format) is the OASIS-standardized
JSON schema for static-analysis findings. Output produced here is compatible
with:

  - VS Code's Problems pane (via the "SARIF Viewer" extension)
  - GitHub Code Scanning (upload via `github/codeql-action/upload-sarif`)
  - GitLab CI's security dashboard
  - Azure DevOps Security Tab
  - any SARIF-aware tool

The exporter folds *every* pillar's findings into a single SARIF log, with
each pillar mapped to a SARIF ``run`` (a SARIF log can contain multiple
runs from different tools, which is exactly Ophamin's situation: one
Empirical Audit Record carries ruff + bandit + mypy + … findings).

Severity mapping (Ophamin → SARIF level + securitySeverity):

  CRITICAL → "error"   securitySeverity = 9.5
  HIGH     → "error"   securitySeverity = 8.0
  MEDIUM   → "warning" securitySeverity = 5.0
  LOW      → "note"    securitySeverity = 2.0
  INFO     → "note"    securitySeverity = 0.5

The original Ophamin signature is preserved in the SARIF
``invocations.properties.ophamin_signature`` so downstream tools can trace
back to the signed Ophamin record.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SARIF_VERSION = "2.1.0"
SARIF_SCHEMA = (
    "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/"
    "master/Schemata/sarif-schema-2.1.0.json"
)

# Ophamin severity → (sarif level, sarif securitySeverity, sarif rank)
_SEVERITY_MAP = {
    "critical": ("error",   "9.5", 95),
    "high":     ("error",   "8.0", 80),
    "medium":   ("warning", "5.0", 50),
    "low":      ("note",    "2.0", 20),
    "info":     ("note",    "0.5",  5),
}


def _level_for(severity: str) -> tuple[str, str, int]:
    return _SEVERITY_MAP.get(
        severity.lower(),
        ("warning", "5.0", 50),  # conservative default for unknown labels
    )


def _repo_root(start: str) -> Path | None:
    """Walk up from a path to the git repository root (the dir containing
    ``.git``). Self-contained — no subprocess — and returns None when no
    ``.git`` ancestor exists (e.g. auditing a directory outside any repo)."""
    if not start:
        return None
    try:
        p = Path(start).resolve()
    except (OSError, ValueError, RuntimeError):
        return None
    if p.is_file():
        p = p.parent
    for candidate in (p, *p.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _src_root_for(record: dict[str, Any]) -> Path | None:
    """Determine the repo root spanning this audit, so SARIF artifact URIs can be
    emitted relative to it. Repo-relative URIs are what GitHub Code Scanning,
    GitLab, and the VS Code SARIF viewer map to source files; absolute file://
    URIs (the producer-side path) map to nothing on the consumer. Anchors on the
    record's declared target first, then the first absolute finding path."""
    target = (record.get("target") or {}).get("target_path") or ""
    root = _repo_root(target)
    if root is not None:
        return root
    for pillar in record.get("pillars", []) or []:
        for f in pillar.get("findings", []) or []:
            path = f.get("path", "")
            if path and not path.startswith("<dependency:") and Path(path).is_absolute():
                root = _repo_root(path)
                if root is not None:
                    return root
    return None


def _file_uri(path: str, src_root: Path | None = None) -> str:
    """Convert a filesystem path into a SARIF artifactLocation URI.

    When ``src_root`` is given and ``path`` lives under it, emits a repo-relative
    POSIX URI — portable across SARIF consumers, which resolve repo-relative
    paths against the analyzed checkout. Falls back to an absolute file:// URI
    for paths outside the repo (e.g. a venv dependency) or when no root is known.
    """
    if not path:
        return ""
    if path.startswith("<dependency:"):
        # pip-audit findings have synthetic <dependency:pkg> paths — keep as-is
        return path
    p = Path(path)
    if src_root is not None and p.is_absolute():
        try:
            return p.resolve().relative_to(src_root).as_posix()
        except (ValueError, OSError):
            pass  # outside src_root — fall through to an absolute URI
    return p.as_uri() if p.is_absolute() else path


def _build_rule(rule_id: str, finding_sample: dict[str, Any]) -> dict[str, Any]:
    """Build a reportingDescriptor (SARIF rule) entry for a rule_id."""
    return {
        "id": rule_id or "ophamin/unknown",
        "name": rule_id or "ophamin/unknown",
        "shortDescription": {"text": rule_id or "(no rule id)"},
        "fullDescription": {
            "text": finding_sample.get("message") or rule_id,
        },
        "help": {
            "text": finding_sample.get("message") or "",
            "markdown": (
                f"`{rule_id}` — see "
                f"`{finding_sample.get('extra', {}).get('url', '')}`"
                if finding_sample.get('extra', {}).get('url')
                else finding_sample.get("message") or ""
            ),
        },
    }


def _build_result(finding: dict[str, Any], src_root: Path | None = None) -> dict[str, Any]:
    """Build a SARIF result entry from one Ophamin Finding dict."""
    severity = finding.get("severity", "low")
    level, sec_severity, rank = _level_for(severity)
    location: dict[str, Any] = {
        "physicalLocation": {
            "artifactLocation": {"uri": _file_uri(finding.get("path", ""), src_root)},
        },
    }
    line = int(finding.get("line", 0) or 0)
    column = int(finding.get("column", 0) or 0)
    if line > 0:
        region = {"startLine": line}
        if column > 0:
            region["startColumn"] = column
        location["physicalLocation"]["region"] = region
    return {
        "ruleId": finding.get("rule_id") or "ophamin/unknown",
        "level": level,
        "rank": rank,
        "message": {"text": finding.get("message", "")},
        "locations": [location],
        "properties": {
            "ophamin_severity": severity,
            "ophamin_pillar": finding.get("pillar_name", ""),
            "security-severity": sec_severity,
        },
    }


def _build_run_for_pillar(pillar: dict[str, Any], record: dict[str, Any], src_root: Path | None = None) -> dict[str, Any] | None:
    """One SARIF run per pillar — but only when the pillar status is 'ok'.

    Unavailable / errored pillars are surfaced in invocations.properties so
    downstream tools see honestly which pillars ran. Returns None for empty
    runs (no findings AND no diagnostic value).
    """
    findings: list[dict[str, Any]] = list(pillar.get("findings", []) or [])
    rule_index: dict[str, dict[str, Any]] = {}
    for f in findings:
        rule_id = f.get("rule_id") or "ophamin/unknown"
        if rule_id not in rule_index:
            rule_index[rule_id] = _build_rule(rule_id, f)

    invocation = {
        "executionSuccessful": pillar.get("status") == "ok",
        "exitCode": pillar.get("exit_code") if pillar.get("exit_code") is not None else 0,
        "wallTimeSeconds": pillar.get("wall_time_s", 0.0),
        "properties": {
            "ophamin_status": pillar.get("status"),
            "ophamin_signature": record.get("signature", ""),
            "ophamin_audit_id": record.get("audit_id", ""),
        },
    }
    if pillar.get("error_message"):
        invocation["properties"]["ophamin_error_message"] = pillar["error_message"]

    return {
        "tool": {
            "driver": {
                "name": pillar.get("tool_name") or pillar.get("pillar_name", "ophamin-pillar"),
                "version": pillar.get("tool_version", ""),
                "informationUri": "https://github.com/IdirBenSlama/ophamin",
                "rules": list(rule_index.values()),
            },
        },
        "invocations": [invocation],
        "results": [_build_result(f, src_root) for f in findings],
        "properties": {
            "ophamin_pillar": pillar.get("pillar_name"),
            "ophamin_pillar_status": pillar.get("status"),
        },
    }


def audit_record_to_sarif(record: dict[str, Any]) -> dict[str, Any]:
    """Convert an Audit Record dict (as produced by AuditRecord.to_dict()) into
    a SARIF 2.1.0 log dict.

    Returns the SARIF dict; caller serializes with json.dump.
    """
    if not isinstance(record, dict):
        raise TypeError("audit_record_to_sarif expects a dict")
    if "pillars" not in record or "audit_id" not in record:
        raise ValueError(
            "input does not look like an Audit Record "
            "(missing 'pillars' and/or 'audit_id')"
        )

    src_root = _src_root_for(record)

    runs: list[dict[str, Any]] = []
    for pillar in record.get("pillars", []):
        run = _build_run_for_pillar(pillar, record, src_root)
        if run is not None:
            runs.append(run)

    return {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": runs,
        # SARIF allows top-level properties bag for tool-specific metadata
        "properties": {
            "ophamin_audit_id": record.get("audit_id"),
            "ophamin_schema_version": record.get("schema_version"),
            "ophamin_signature": record.get("signature"),
            "ophamin_target_path": record.get("target", {}).get("target_path"),
            "ophamin_target_content_hash": record.get("target", {}).get(
                "target_content_hash"
            ),
            # repo root the artifact URIs are relative to (None ⇒ URIs stay
            # absolute file:// because no .git ancestor was found)
            "ophamin_src_root": str(src_root) if src_root is not None else None,
        },
    }


class SARIFExporter:
    """Wrap ``audit_record_to_sarif`` in a Renderer-shaped class for symmetry
    with reporting/ and ergonomic CLI access.

    Audit records only; proof records use ``JUnitXMLExporter``.
    """

    def export(self, audit_record: dict[str, Any], out_path: str | Path) -> Path:
        sarif = audit_record_to_sarif(audit_record)
        out = Path(out_path)
        if out.suffix.lower() != ".sarif":
            out = out.with_suffix(".sarif")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(sarif, indent=2, default=str), encoding="utf-8")
        return out
