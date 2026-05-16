"""Format codec for :class:`AuditRecord` — Move H parallel to Move B's
proof codec.

Mirrors :mod:`ophamin.measuring.proof.codec` exactly so audit records
get the same load / validate / verify / ingest treatment proof records
do. The differences:

- No JSON-Schema validation today (audit records don't ship a
  ``schema.json`` alongside; structural validation is via the
  ``AuditRecord.from_dict`` parser).
- No threshold/verdict — audits are descriptive by default. The
  validation layer focuses on signature + body-roundtrip integrity +
  schema_version compatibility.

Per the framework's no-fallback rule, every failure raises a typed
:class:`AuditCodecError` subclass with a descriptive message.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from ophamin.auditing.audit_record import (
    AuditRecord,
    SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
)


# --- typed errors -----------------------------------------------------------


class AuditCodecError(RuntimeError):
    """Base class for every audit-codec failure mode."""


class AuditDecodeError(AuditCodecError):
    """The file at the given path is not loadable as an audit record.

    Covers: file-not-found, OS errors, JSON syntax errors, and
    structural :class:`KeyError` / :class:`ValueError` raised by
    :meth:`AuditRecord.from_dict` on a malformed payload.
    """


class AuditSignatureError(AuditCodecError):
    """HMAC signature verification failed (or was required but skipped).

    Raised by :func:`ingest` when ``strict_signature=True`` and either
    no key was provided or the key did not validate the record's
    signature.
    """


class AuditSchemaVersionMismatchError(AuditCodecError):
    """The record's ``schema_version`` does not match the required version.

    Default: :func:`ingest` requires the version match
    :data:`SCHEMA_VERSION`. Pass ``require_schema_version=None`` to
    accept any version (e.g. for migration tooling).
    """


# --- validation report shape ------------------------------------------------


@dataclass(frozen=True)
class AuditValidationReport:
    """Outcome of :func:`validate` — structural + signature layers."""

    record_ok: bool
    record_problems: tuple[str, ...]
    signature_ok: bool | None

    @property
    def all_ok(self) -> bool:
        if not self.record_ok:
            return False
        if self.signature_ok is False:
            return False
        return True


# --- single-record IO -------------------------------------------------------


def dump(
    record: AuditRecord,
    path: str | Path,
    *,
    indent: int = 2,
) -> Path:
    """Write ``record`` to ``path`` as canonical JSON. Returns the path.

    Creates the parent directory if it doesn't already exist. Raises
    :class:`OSError` if the write fails — codec does NOT swallow
    file-system errors.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(record.to_dict(), indent=indent, default=str),
        encoding="utf-8",
    )
    return p


def load(path: str | Path) -> AuditRecord:
    """Load + reconstruct an :class:`AuditRecord` from ``path``.

    Raises :class:`AuditDecodeError` on file-system errors, malformed
    JSON, or a structurally incomplete payload. The chained exception
    preserves the underlying error for forensic debugging.
    """
    p = Path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditDecodeError(
            f"could not read audit JSON from {p}: {exc}"
        ) from exc
    try:
        return AuditRecord.from_dict(data)
    except (KeyError, ValueError, TypeError) as exc:
        raise AuditDecodeError(
            f"malformed audit record at {p}: {exc}"
        ) from exc


def verify_signature(path: str | Path, key: bytes) -> bool:
    """Load the record at ``path`` + verify its HMAC-SHA256 signature.

    Returns True iff the signature matches the record body under
    ``key``. False if signature is empty or doesn't match.

    Raises :class:`AuditDecodeError` if the file itself can't be
    loaded.
    """
    record = load(path)
    return record.verify_signature(key)


def _structural_problems(record: AuditRecord) -> tuple[str, ...]:
    """Return a tuple of structural problems with ``record``.

    Empty tuple means the record is well-formed. Mirrors the spirit of
    :meth:`EmpiricalProofRecord.validate` — basic shape checks that
    augment the from_dict parser's loudness.
    """
    problems: list[str] = []
    if not record.target_path:
        problems.append("target_path is empty")
    if not record.target_content_hash:
        problems.append("target_content_hash is empty")
    if not record.ophamin_version:
        problems.append("ophamin_version is empty")
    if not record.captured_at:
        problems.append("captured_at is empty")
    else:
        try:
            datetime.fromisoformat(record.captured_at)
        except ValueError:
            problems.append("captured_at is not an ISO-8601 timestamp")
    # pillar count from summary must match the pillars list
    pillar_names_in_list = {p.pillar_name for p in record.pillars}
    pillar_names_in_summary = (
        set(record.summary.pillars_run)
        | set(record.summary.pillars_unavailable)
        | set(record.summary.pillars_errored)
    )
    missing_in_summary = pillar_names_in_list - pillar_names_in_summary
    extra_in_summary = pillar_names_in_summary - pillar_names_in_list
    if missing_in_summary:
        problems.append(
            f"pillar(s) in record but not in summary: {sorted(missing_in_summary)}"
        )
    if extra_in_summary:
        problems.append(
            f"pillar(s) in summary but not in record: {sorted(extra_in_summary)}"
        )
    return tuple(problems)


def validate(
    path: str | Path,
    *,
    key: bytes | None = None,
) -> AuditValidationReport:
    """Run structural + (optional) signature validation in one call.

    Returns a :class:`AuditValidationReport`. Does NOT raise on any
    validation failure — caller inspects the report's ``all_ok``
    property + ``record_problems`` tuple to decide what to do. Use
    :func:`ingest` for the raise-on-any-failure variant.

    The structural check (via :meth:`AuditRecord.from_dict` + the
    in-module ``_structural_problems`` helper) runs first; if the
    record can't be loaded, the report carries the decode error as
    a single record-problem string. When loaded, the in-module shape
    check augments with cross-section consistency (e.g. pillars in
    record vs summary).
    """
    try:
        record = load(path)
    except AuditDecodeError as exc:
        return AuditValidationReport(
            record_ok=False,
            record_problems=(str(exc),),
            signature_ok=None,
        )
    problems = _structural_problems(record)
    signature_ok: bool | None
    if key is None:
        signature_ok = None
    else:
        signature_ok = record.verify_signature(key)
    return AuditValidationReport(
        record_ok=not problems,
        record_problems=problems,
        signature_ok=signature_ok,
    )


def ingest(
    path: str | Path,
    *,
    key: bytes | None = None,
    strict_signature: bool = False,
    require_schema_version: str | None = None,
    allowed_schema_versions: tuple[str, ...] | None = None,
) -> AuditRecord:
    """Single-call load + full-validate + optional signature-verify.

    The boundary function for accepting third-party audit records.
    After a successful call, the returned :class:`AuditRecord` is
    guaranteed:

    - structurally well-formed (record-validate-clean),
    - schema-version in the accepted set (default: every version
      declared in :data:`SUPPORTED_SCHEMA_VERSIONS`),
    - signature-verified IFF ``strict_signature=True`` and a ``key``
      was provided.

    Args:
        path: file path to the audit JSON.
        key: HMAC key for signature verification.
        strict_signature: when True, require key + valid signature
            or raise loud.
        require_schema_version: backward-compatibility — if set,
            requires an exact match (legacy callers).
        allowed_schema_versions: accepted set (default: all supported
            versions per :data:`SUPPORTED_SCHEMA_VERSIONS`).

    Raises:
        AuditCodecError: structural validation failed.
        AuditSchemaVersionMismatchError: schema_version isn't in the
            accepted set.
        AuditSignatureError: strict_signature=True and either no key
            was provided or signature verification failed.
    """
    record = load(path)
    problems = _structural_problems(record)
    p = Path(path)
    if problems:
        raise AuditCodecError(
            f"structural validation failed for {p}:\n  - "
            + "\n  - ".join(problems)
        )
    if require_schema_version is not None:
        if record.schema_version != require_schema_version:
            raise AuditSchemaVersionMismatchError(
                f"audit at {p} has schema_version {record.schema_version!r}; "
                f"required {require_schema_version!r}"
            )
    else:
        accepted = allowed_schema_versions or SUPPORTED_SCHEMA_VERSIONS
        if record.schema_version not in accepted:
            raise AuditSchemaVersionMismatchError(
                f"audit at {p} has schema_version {record.schema_version!r}; "
                f"accepted: {list(accepted)}"
            )
    if strict_signature:
        if key is None:
            raise AuditSignatureError(
                f"strict_signature=True for {p} but no key was provided"
            )
        if not record.verify_signature(key):
            raise AuditSignatureError(
                f"strict_signature=True for {p} but signature did not "
                f"verify under the provided key"
            )
    return record


# --- directory walking ------------------------------------------------------


def iter_audits(directory: str | Path) -> Iterator[Path]:
    """Yield every ``*.json`` file under ``directory`` (recursive).

    Order is sorted-path-deterministic for stable consumers.
    """
    yield from sorted(Path(directory).rglob("*.json"))


@dataclass(frozen=True)
class AuditListEntry:
    """One row in the output of :func:`list_audits`."""

    path: Path
    audit_id: str | None = None
    total_findings: int | None = None
    schema_version: str | None = None
    target_path: str | None = None
    signature_ok: bool | None = None
    error: str | None = None


def list_audits(
    directory: str | Path,
    *,
    key: bytes | None = None,
) -> tuple[AuditListEntry, ...]:
    """Walk ``directory`` recursively; emit one summary entry per JSON.

    A file that fails to decode produces an entry with ``error`` set
    and the other content fields ``None``. Mirrors
    :func:`ophamin.measuring.proof.codec.list_proofs`.
    """
    entries: list[AuditListEntry] = []
    for path in iter_audits(directory):
        try:
            record = load(path)
        except AuditDecodeError as exc:
            entries.append(AuditListEntry(path=path, error=str(exc)))
            continue
        signature_ok: bool | None
        if key is None:
            signature_ok = None
        else:
            signature_ok = record.verify_signature(key)
        entries.append(
            AuditListEntry(
                path=path,
                audit_id=record.audit_id,
                total_findings=record.summary.total_findings,
                schema_version=record.schema_version,
                target_path=record.target_path,
                signature_ok=signature_ok,
            )
        )
    return tuple(entries)


__all__ = [
    "AuditCodecError",
    "AuditDecodeError",
    "AuditListEntry",
    "AuditSchemaVersionMismatchError",
    "AuditSignatureError",
    "AuditValidationReport",
    "dump",
    "ingest",
    "iter_audits",
    "list_audits",
    "load",
    "validate",
    "verify_signature",
]
