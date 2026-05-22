"""Format codec for :class:`EmpiricalProofRecord` — the single canonical
load / validate / verify / ingest surface.

The proof-record component dataclasses already declare ``to_dict`` /
``from_dict`` round-trip pairs, and :class:`EmpiricalProofRecord` ships
``to_json`` / ``from_json`` file shortcuts. This module collects them
into one **loud-failure** interface that bundles:

* JSON-Schema validation against ``proof/schema.json``;
* the structural ``record.validate()`` checklist (falsifiable +
  pre-registered + traceable + reproducible + attributed);
* optional HMAC-SHA256 signature verification under a caller-provided key;
* one-call ``ingest`` that runs all three and raises loud on the first
  failure;
* directory-walking ``iter_proofs`` / ``list_proofs`` so the proof
  corpus on disk has a first-class Python interface.

Per the framework's no-fallback rule: every failure mode raises a
typed :class:`ProofCodecError` subclass with a descriptive message; the
codec does not return ``None`` or empty dicts on error and does not
swallow exceptions.

Read alongside :class:`EmpiricalProofRecord` itself
(``src/ophamin/measuring/proof/record.py``) and the JSON Schema
(``src/ophamin/measuring/proof/schema.json``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from ophamin.measuring.proof.record import (
    SCHEMA_VERSION,
    EmpiricalProofRecord,
)

#: absolute path to the official JSON Schema (re-exported here for codec
#: callers that want the file location without importing the schema text).
SCHEMA_PATH = Path(__file__).with_name("schema.json")


# --- typed errors -----------------------------------------------------------


class ProofCodecError(RuntimeError):
    """Base class for every codec failure mode.

    Catching this broad class lets callers handle any codec error
    uniformly; subclasses below are the load-bearing distinctions for
    callers that want to handle each failure separately.
    """


class ProofDecodeError(ProofCodecError):
    """The file at the given path is not loadable as a proof record.

    Covers: file-not-found, OS errors, JSON syntax errors, and
    structural :class:`KeyError` / :class:`ValueError` raised by
    :meth:`EmpiricalProofRecord.from_dict` on a malformed payload.
    """


class ProofSchemaError(ProofCodecError):
    """The on-disk JSON does not validate against the official JSON Schema.

    Indicates the file is structurally wrong at the JSON-Schema level —
    e.g. a required field is missing, an enum value is unknown, a type
    is wrong. The ``schema_errors`` attribute carries every per-path
    error the schema validator surfaced (not just the first).
    """

    def __init__(self, path: Path, errors: tuple[str, ...]) -> None:
        self.path = path
        self.schema_errors = errors
        super().__init__(
            f"JSON-Schema validation failed for {path}:\n  - "
            + "\n  - ".join(errors)
        )


class ProofValidationError(ProofCodecError):
    """The record loaded cleanly but failed :meth:`record.validate`.

    Covers structural-integrity problems above the JSON-Schema layer —
    e.g. pre-registration timestamp after the created-at timestamp,
    verdict contradicting the threshold, evidence missing library
    attribution.
    """

    def __init__(self, path: Path, problems: tuple[str, ...]) -> None:
        self.path = path
        self.record_problems = problems
        super().__init__(
            f"record structural validation failed for {path}:\n  - "
            + "\n  - ".join(problems)
        )


class ProofSignatureError(ProofCodecError):
    """HMAC signature verification failed (or was required but skipped).

    Raised by :func:`ingest` when ``strict_signature=True`` and either no
    key was provided or the key did not validate the record's
    signature.
    """


class ProofSchemaVersionMismatchError(ProofCodecError):
    """The record's ``schema_version`` does not match the required version.

    Default: :func:`ingest` requires the version match
    :data:`SCHEMA_VERSION`. Pass ``require_schema_version=None`` to opt
    out of the version gate (e.g. when accepting a third-party proof
    written against an older schema and the caller has a migration
    path in mind).
    """


# --- validation report shape ------------------------------------------------


@dataclass(frozen=True)
class ValidationReport:
    """Structured outcome of :func:`validate` — all three checks rolled up.

    Frozen so callers can pass it around without worrying about mutation.

    Fields:

    - ``schema_ok`` / ``schema_errors`` — JSON-Schema layer.
    - ``record_ok`` / ``record_problems`` — :meth:`record.validate` layer.
    - ``signature_ok`` — HMAC layer. ``None`` when no key was provided
      (signature check was skipped, not failed); ``True`` / ``False``
      when a key was provided.

    The :attr:`all_ok` property is the headline: a proof is "fully
    valid" iff schema + record both pass AND signature is either
    verified or not checked.
    """

    schema_ok: bool
    schema_errors: tuple[str, ...]
    record_ok: bool
    record_problems: tuple[str, ...]
    signature_ok: bool | None

    @property
    def all_ok(self) -> bool:
        if not self.schema_ok:
            return False
        if not self.record_ok:
            return False
        if self.signature_ok is False:
            return False
        return True


# --- single-record IO -------------------------------------------------------


def dump(
    record: EmpiricalProofRecord,
    path: str | Path,
    *,
    indent: int = 2,
) -> Path:
    """Write ``record`` to ``path`` as canonical JSON. Returns the path.

    Creates the parent directory if it doesn't already exist (mirrors
    the convenience pattern of ``pathlib.Path.write_text`` callers
    typically wrap).

    Raises :class:`OSError` if the write fails — codec does NOT swallow
    file-system errors. Use the higher-level CLI / orchestration layer
    if structured error handling is wanted.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(record.to_dict(), indent=indent, default=str),
        encoding="utf-8",
    )
    return p


def load(path: str | Path) -> EmpiricalProofRecord:
    """Load + reconstruct an :class:`EmpiricalProofRecord` from ``path``.

    Raises :class:`ProofDecodeError` on file-system errors, malformed
    JSON, or a structurally incomplete payload. The chained exception
    preserves the underlying error for forensic debugging.
    """
    p = Path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProofDecodeError(
            f"could not read proof JSON from {p}: {exc}"
        ) from exc
    try:
        return EmpiricalProofRecord.from_dict(data)
    except (KeyError, ValueError, TypeError) as exc:
        raise ProofDecodeError(
            f"malformed proof record at {p}: {exc}"
        ) from exc


# --- validation ------------------------------------------------------------


def _load_schema() -> dict[str, Any]:
    """Read the official JSON Schema document. Cached at first call."""
    if not hasattr(_load_schema, "_cached"):
        _load_schema._cached = json.loads(  # type: ignore[attr-defined]
            SCHEMA_PATH.read_text(encoding="utf-8")
        )
    cached: dict[str, Any] = _load_schema._cached  # type: ignore[attr-defined]
    return cached


def validate_schema(path: str | Path) -> tuple[bool, tuple[str, ...]]:
    """Validate the JSON file against the official proof-record schema.

    Returns ``(ok, errors)``. ``errors`` is a tuple of human-readable
    error strings, each ``"<json-pointer>: <message>"``. Empty tuple
    on success.

    Uses ``jsonschema`` (Draft 2020-12 validator). Does NOT raise on
    schema-level failure — caller decides whether to escalate. Does
    raise :class:`ProofDecodeError` if the file itself can't be read.
    """
    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover — required core dep
        raise RuntimeError(
            "jsonschema is required for proof-record schema validation; "
            "install via `pip install jsonschema`"
        ) from exc

    p = Path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProofDecodeError(
            f"could not read proof JSON from {p}: {exc}"
        ) from exc

    validator = jsonschema.Draft202012Validator(_load_schema())
    errors = tuple(
        (
            f"{'.'.join(str(part) for part in err.absolute_path) or '<root>'}: "
            f"{err.message}"
        )
        for err in validator.iter_errors(data)
    )
    return (not errors), errors


def verify_signature(path: str | Path, key: bytes) -> bool:
    """Load the record at ``path`` + verify its HMAC-SHA256 signature.

    Returns True iff the signature matches the record body under
    ``key``. False if signature is empty or doesn't match.

    Raises :class:`ProofDecodeError` if the file itself can't be
    loaded. Does NOT raise on signature mismatch — caller decides
    whether to escalate (use :func:`ingest` with
    ``strict_signature=True`` for the loud-failure variant).
    """
    record = load(path)
    return record.verify_signature(key)


def validate(
    path: str | Path,
    *,
    key: bytes | None = None,
) -> ValidationReport:
    """Run schema + record + (optional) signature validation in one call.

    Returns a :class:`ValidationReport` capturing every layer's result.
    Does NOT raise on any validation failure — caller inspects the
    report's ``all_ok`` property and ``schema_errors`` /
    ``record_problems`` tuples to decide what to do.

    Use :func:`ingest` for the raise-on-any-failure variant.

    The JSON-Schema check runs first; if the schema is broken, the
    structural ``record.validate`` is skipped (a malformed-at-schema
    payload can't be safely reconstructed into a record). When
    schema-ok, the record is loaded and ``record.validate`` is
    invoked; if a ``key`` was provided, signature verification runs
    too. The ``signature_ok`` field is ``None`` when no key was
    provided (i.e. the check was skipped), ``True`` / ``False`` when
    a key was provided.
    """
    schema_ok, schema_errors = validate_schema(path)
    if not schema_ok:
        return ValidationReport(
            schema_ok=False,
            schema_errors=schema_errors,
            record_ok=False,
            record_problems=(
                "schema validation failed; structural checks skipped",
            ),
            signature_ok=None,
        )
    record = load(path)
    record_problems = tuple(record.validate())
    signature_ok: bool | None
    if key is None:
        signature_ok = None
    else:
        signature_ok = record.verify_signature(key)
    return ValidationReport(
        schema_ok=True,
        schema_errors=(),
        record_ok=not record_problems,
        record_problems=record_problems,
        signature_ok=signature_ok,
    )


def ingest(
    path: str | Path,
    *,
    key: bytes | None = None,
    strict_signature: bool = False,
    require_schema_version: str | None = SCHEMA_VERSION,
) -> EmpiricalProofRecord:
    """Single-call load + full-validate + optional signature-verify.

    The boundary function for accepting third-party proof records.
    After a successful call, the returned :class:`EmpiricalProofRecord`
    is guaranteed:

    - structurally well-formed (JSON-Schema validated),
    - record-validate-clean (no internal contradictions),
    - schema-version matches ``require_schema_version`` (unless that's
      ``None``, which opts out of the version gate),
    - signature-verified IFF ``strict_signature=True`` was passed AND
      a ``key`` was provided.

    On any failure, raises the matching :class:`ProofCodecError`
    subclass with a descriptive message. The caller never has to
    inspect a partial / fallback record.

    Args:
        path: file path to the proof JSON.
        key: optional HMAC-SHA256 key for signature verification.
        strict_signature: when True, require ``key`` to be provided AND
            the signature to verify. Default False — signature is
            checked when key is provided but verification failure is
            not fatal (matches the ``validate`` shape).
        require_schema_version: required schema version. Default is
            the current :data:`SCHEMA_VERSION`; pass ``None`` to
            accept any version (e.g. for migration tooling).

    Raises:
        ProofSchemaError: JSON-Schema validation failed.
        ProofValidationError: structural ``record.validate`` failed.
        ProofSchemaVersionMismatchError: ``schema_version`` didn't
            match ``require_schema_version``.
        ProofSignatureError: ``strict_signature=True`` and either no
            key was provided or signature verification failed.
        ProofDecodeError: file couldn't be read or JSON couldn't be
            decoded (raised by underlying :func:`load`).
    """
    report = validate(path, key=key)
    p = Path(path)
    if not report.schema_ok:
        raise ProofSchemaError(p, report.schema_errors)
    if not report.record_ok:
        raise ProofValidationError(p, report.record_problems)
    record = load(p)
    if require_schema_version is not None and record.schema_version != require_schema_version:
        raise ProofSchemaVersionMismatchError(
            f"proof at {p} has schema_version "
            f"{record.schema_version!r}; required "
            f"{require_schema_version!r}"
        )
    if strict_signature:
        if key is None:
            raise ProofSignatureError(
                f"strict_signature=True for {p} but no key was provided"
            )
        if report.signature_ok is not True:
            raise ProofSignatureError(
                f"strict_signature=True for {p} but signature did not "
                f"verify under the provided key"
            )
    return record


# --- directory walking ------------------------------------------------------


#: Subdirectories under a proofs root that hold non-proof JSON and must
#: be skipped by proof iteration. ``llm_calls/`` holds the agentic
#: layer's signed ``LLMCallRecord`` audit records (0.63.0+) — a
#: different schema (call_id / task / request / response, not proof_id /
#: claim / verdict). They live under ``proofs/`` for audit-trail
#: locality but are NOT ``EmpiricalProofRecord``s; scanning them as
#: proofs mis-classifies them (and fails schema validation).
_NON_PROOF_SUBDIRS: frozenset[str] = frozenset({"llm_calls"})

#: Sibling JSON filenames that live *inside* a proof bundle directory but are
#: NOT ``EmpiricalProofRecord``s. ``diagnosis.json`` is the agentic diagnosis
#: layer's analysis artifact (model / latency_ms / diagnosis / proof_ids — a
#: different schema), persisted next to ``proof.json`` for locality. The
#: subdir skip above can't catch it because it's a sibling file, not a
#: subtree — so it gets its own filename skip. Same intent: agentic-layer
#: artifacts are not mistaken for proofs (which would fail schema validation).
_NON_PROOF_FILENAMES: frozenset[str] = frozenset({"diagnosis.json"})


def iter_proofs(directory: str | Path) -> Iterator[Path]:
    """Yield every proof ``*.json`` file under ``directory`` (recursive).

    Order is sorted-path-deterministic so consumers (e.g.
    :func:`list_proofs`, ``ophamin summarize``, drift detectors) see a
    stable enumeration.

    Skips the :data:`_NON_PROOF_SUBDIRS` subtrees (currently ``llm_calls/``)
    and the :data:`_NON_PROOF_FILENAMES` sibling artifacts (currently
    ``diagnosis.json``) so agentic-layer records aren't mistaken for proofs.
    """
    for p in sorted(Path(directory).rglob("*.json")):
        if _NON_PROOF_SUBDIRS.intersection(p.parts):
            continue
        if p.name in _NON_PROOF_FILENAMES:
            continue
        yield p


@dataclass(frozen=True)
class ProofListEntry:
    """One row in the output of :func:`list_proofs`.

    ``error`` is populated only when the record at ``path`` could not
    be decoded (file unreadable, JSON malformed, missing required
    fields). All other fields are ``None`` in that case.

    ``signature_ok`` is ``None`` when no key was provided.
    """

    path: Path
    proof_id: str | None = None
    verdict: str | None = None
    schema_version: str | None = None
    claim_statement: str | None = None
    signature_ok: bool | None = None
    error: str | None = None


@dataclass(frozen=True)
class ProofIndex:
    """Master index of a proof corpus on disk.

    Output of :func:`build_index` — aggregates every proof under a
    directory into a verdict-grouped + family-grouped manifest. Use
    :meth:`to_markdown` to render the conventional ``INDEX.md`` form.

    ``by_family`` is a heuristic grouping by filename prefix (legacy
    proofs lack the structured tier/family fields Move A introduced
    on the ``Scenario`` class; that metadata is not yet surfaced into
    :class:`EmpiricalProofRecord`'s identity section — a follow-on
    Move). For proofs written before that follow-on, the family tag
    is derived from the filename's first underscore-separated segment.
    """

    root: Path
    generated_at: str
    total: int
    n_decode_errors: int
    by_verdict: dict[str, int]
    by_family: dict[str, int]
    entries: tuple[ProofListEntry, ...]

    def to_markdown(self) -> str:
        """Render the index as a human-readable Markdown manifest.

        The conventional location is ``<root>/INDEX.md``; this method
        produces the file's contents.
        """
        lines: list[str] = []
        lines.append(f"# Proof corpus index — `{self.root}`")
        lines.append("")
        lines.append(f"_Generated: {self.generated_at}_")
        lines.append("")
        lines.append(
            f"**{self.total} record(s)** "
            f"({self.n_decode_errors} decode error(s))."
        )
        lines.append("")

        if self.by_verdict:
            lines.append("## By verdict")
            lines.append("")
            lines.append("| Verdict | Count |")
            lines.append("|---|---|")
            for verdict in sorted(self.by_verdict):
                lines.append(f"| {verdict} | {self.by_verdict[verdict]} |")
            lines.append("")

        if self.by_family:
            lines.append("## By family (heuristic from filename)")
            lines.append("")
            lines.append("| Family | Count |")
            lines.append("|---|---|")
            for family in sorted(self.by_family):
                lines.append(f"| {family} | {self.by_family[family]} |")
            lines.append("")

        if self.entries:
            lines.append("## All records")
            lines.append("")
            lines.append("| Verdict | Schema | Path | Claim |")
            lines.append("|---|---|---|---|")
            for e in self.entries:
                rel = e.path.relative_to(self.root) if self.root in e.path.parents or e.path == self.root else e.path
                if e.error:
                    lines.append(
                        f"| `ERROR` | — | `{rel}` | _{e.error}_ |"
                    )
                    continue
                claim_snippet = (e.claim_statement or "").replace("\n", " ").replace("|", "\\|")
                if len(claim_snippet) > 100:
                    claim_snippet = claim_snippet[:97] + "..."
                lines.append(
                    f"| {e.verdict or '?'} | {e.schema_version or '?'} "
                    f"| `{rel}` | {claim_snippet} |"
                )
            lines.append("")

        return "\n".join(lines)


def _family_from_filename(path: Path) -> str:
    """Heuristic family extraction from a proof's filename.

    Legacy proofs predate the structured ``Scenario.family`` field; the
    family is inferred from the first underscore-separated segment of
    the stem (e.g. ``immune_siege_entity_<hash>.json`` → ``immune``).
    A future Move will surface ``cls.family`` into the proof record
    itself; until then this is the cross-version fallback.
    """
    stem = path.stem
    if "_" not in stem:
        return stem
    return stem.split("_", 1)[0]


def build_index(directory: str | Path, *, key: bytes | None = None) -> ProofIndex:
    """Walk ``directory`` recursively and build a :class:`ProofIndex`.

    The index aggregates per-verdict + per-family counts and carries
    the full underlying :class:`ProofListEntry` tuple. Decode errors
    surface as entries with ``error`` set; the walk does NOT stop on
    the first bad file (mirrors :func:`list_proofs`).

    Pass ``key=`` to also include signature verification in each
    entry. Per-record signature state does not enter the aggregated
    counts in this version — pure schema + verdict + family grouping.
    """
    from datetime import datetime, timezone

    root = Path(directory)
    entries = list_proofs(root, key=key)
    by_verdict: dict[str, int] = {}
    by_family: dict[str, int] = {}
    n_decode_errors = 0
    for entry in entries:
        if entry.error:
            n_decode_errors += 1
            by_verdict.setdefault("ERROR", 0)
            by_verdict["ERROR"] += 1
            continue
        verdict = entry.verdict or "UNKNOWN"
        by_verdict.setdefault(verdict, 0)
        by_verdict[verdict] += 1
        family = _family_from_filename(entry.path)
        by_family.setdefault(family, 0)
        by_family[family] += 1
    return ProofIndex(
        root=root,
        generated_at=datetime.now(timezone.utc).isoformat(),
        total=len(entries),
        n_decode_errors=n_decode_errors,
        by_verdict=by_verdict,
        by_family=by_family,
        entries=entries,
    )


def list_proofs(
    directory: str | Path,
    *,
    key: bytes | None = None,
) -> tuple[ProofListEntry, ...]:
    """Walk ``directory`` recursively and return one summary entry per JSON.

    A file that fails to decode produces an entry with ``error`` set
    and the other content fields ``None`` — the walk does NOT stop on
    a bad file. Use :func:`ingest` against an individual path when you
    need loud-failure semantics for a single record.
    """
    entries: list[ProofListEntry] = []
    for path in iter_proofs(directory):
        try:
            record = load(path)
        except ProofDecodeError as exc:
            entries.append(ProofListEntry(path=path, error=str(exc)))
            continue
        signature_ok: bool | None
        if key is None:
            signature_ok = None
        else:
            signature_ok = record.verify_signature(key)
        entries.append(
            ProofListEntry(
                path=path,
                proof_id=record.proof_id,
                verdict=record.verdict.outcome,
                schema_version=record.schema_version,
                claim_statement=record.claim.statement,
                signature_ok=signature_ok,
            )
        )
    return tuple(entries)


__all__ = [
    "SCHEMA_PATH",
    "SCHEMA_VERSION",
    "ProofCodecError",
    "ProofDecodeError",
    "ProofSchemaError",
    "ProofValidationError",
    "ProofSignatureError",
    "ProofSchemaVersionMismatchError",
    "ValidationReport",
    "ProofListEntry",
    "ProofIndex",
    "dump",
    "load",
    "validate_schema",
    "verify_signature",
    "validate",
    "ingest",
    "iter_proofs",
    "list_proofs",
    "build_index",
]
