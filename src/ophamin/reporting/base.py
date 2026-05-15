"""Base types for the reporting wheel — RecordKind, ReportFormat, ReportRenderer.

Each renderer subclass implements ``render_proof`` and ``render_audit``
against the same source data (the record JSON) but emits a different
serialization. The ``ReportRunner`` picks the right renderer.

Render targets are pure data: a renderer takes a parsed record dict + an
output directory and writes files. No network, no env reads beyond what the
record carries.
"""

from __future__ import annotations

import abc
import json
from enum import Enum
from pathlib import Path
from typing import Any


class RecordKind(str, Enum):
    """What kind of record is being rendered."""

    PROOF = "proof"             # EmpiricalProofRecord (from scenarios)
    AUDIT = "audit"             # AuditRecord (from auditing wheel)
    # future: SCHEMA, DRIFT


class ReportFormat(str, Enum):
    """Output format for the rendered report."""

    HTML = "html"
    MARKDOWN = "markdown"
    LATEX = "latex"
    PDF = "pdf"
    JUPYTER = "jupyter"          # deferred


def load_record(path: str | Path) -> tuple[RecordKind, dict[str, Any]]:
    """Read a record JSON and classify it as PROOF or AUDIT.

    A proof record carries a top-level "claim" + "verdict"; an audit record
    carries "audit_id" + "pillars". The classification is structural, not
    extension-based.
    """
    payload = json.loads(Path(path).read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: not a JSON object — cannot classify as a record")
    if "audit_id" in payload and "pillars" in payload:
        return RecordKind.AUDIT, payload
    if "claim" in payload and "verdict" in payload:
        return RecordKind.PROOF, payload
    raise ValueError(
        f"{path}: not recognisable as an Empirical Proof Record (claim+verdict) "
        f"or an Audit Record (audit_id+pillars). Top-level keys: "
        f"{sorted(payload.keys())[:10]}"
    )


class ReportRenderer(abc.ABC):
    """Render a single record (proof or audit) into one output format.

    Subclasses implement ``render_proof`` and ``render_audit``. The
    ``ReportRunner`` dispatches on RecordKind.
    """

    #: ReportFormat this renderer produces — subclass sets it
    format: ReportFormat

    @abc.abstractmethod
    def render_proof(self, record: dict[str, Any], out_path: Path) -> Path:
        """Render an Empirical Proof Record to ``out_path``. Returns the
        resolved path (which may add an extension or create sidecar files
        in an adjacent assets dir)."""

    @abc.abstractmethod
    def render_audit(self, record: dict[str, Any], out_path: Path) -> Path:
        """Render an Audit Record to ``out_path``."""

    def render(
        self,
        kind: RecordKind,
        record: dict[str, Any],
        out_path: Path,
    ) -> Path:
        """Dispatch on RecordKind."""
        if kind == RecordKind.PROOF:
            return self.render_proof(record, out_path)
        if kind == RecordKind.AUDIT:
            return self.render_audit(record, out_path)
        raise ValueError(f"unsupported RecordKind: {kind}")
