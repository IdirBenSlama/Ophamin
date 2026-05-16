"""AuditRecord — the signed, content-addressable artefact of one audit run.

Parallel to ``EmpiricalProofRecord`` but descriptive by default — audits
don't require a falsifiable claim because the value is in the *findings
distribution* itself, not in passing a threshold. A separate threshold-mode
wrapper can pre-register pass/fail criteria for CI gating; that's a follow-on.

Nine logical sections, mirroring the proof record shape so the two can be
processed by the same downstream tooling (reporting, drift, etc.):

  1. Identity         ophamin version + commit, captured_at, schema version
  2. Target           path being audited + its content hash (for forensics)
  3. Pillars          which pillars ran, which were unavailable, versions
  4. Findings         the union of every pillar's findings (already in
                      PillarResult, but flattened here for cross-pillar
                      hotspot detection)
  5. Summary          aggregate counts + severity histogram + file hotspots
  6. (no verdict)     audits are descriptive; if a claim is wanted, wrap
                      this record in an Empirical Proof Record with a
                      threshold on a chosen statistic
  7. Reproduction     command + env-lock (later)
  8. Provenance       (optional) PROV-O graph of the run
  9. Signature        HMAC-SHA256 over the body
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ophamin import __version__
from ophamin.auditing.base import PillarResult


SCHEMA_VERSION = "audit/1.1"

#: schema versions this codec is willing to accept on read. Older
#: versions are loaded into the current shape with their optional
#: fields defaulting to None (per Move L's backward-compat contract).
SUPPORTED_SCHEMA_VERSIONS: tuple[str, ...] = ("audit/1.0", "audit/1.1")


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ophamin_git_commit() -> str:
    """Best-effort capture of the current Ophamin git commit."""
    here = Path(__file__).resolve().parents[3]
    try:
        result = subprocess.run(
            ["git", "-C", str(here), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def _content_hash_of_target(target_path: str | Path) -> str:
    """SHA-256 of the target file or of every .py file in the target tree
    (sorted by relative path for deterministic ordering).

    For directories, hashes the *list* of (relative_path, file_hash) entries
    — gives a stable fingerprint that changes when any source file changes
    but doesn't depend on filesystem-order tricks.
    """
    path = Path(target_path).resolve()
    if path.is_file():
        return _hash_file(path)
    if not path.is_dir():
        return ""
    entries: list[tuple[str, str]] = []
    for f in path.rglob("*.py"):
        if "__pycache__" in f.parts or ".venv" in f.parts:
            continue
        try:
            rel = str(f.relative_to(path))
            entries.append((rel, _hash_file(f)))
        except (OSError, ValueError):
            continue
    entries.sort()
    return hashlib.sha256(repr(entries).encode("utf-8")).hexdigest()


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()


@dataclass(frozen=True)
class AuditSummary:
    """Cross-pillar aggregate — every pillar's findings rolled up."""

    total_findings: int
    severity_histogram: dict[str, int]
    findings_per_pillar: dict[str, int]
    top_files: list[tuple[str, int]]              # top 20 hotspot files
    pillars_run: tuple[str, ...]
    pillars_unavailable: tuple[str, ...]
    pillars_errored: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_findings": self.total_findings,
            "severity_histogram": self.severity_histogram,
            "findings_per_pillar": self.findings_per_pillar,
            "top_files": list(self.top_files),
            "pillars_run": list(self.pillars_run),
            "pillars_unavailable": list(self.pillars_unavailable),
            "pillars_errored": list(self.pillars_errored),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuditSummary":
        """Reconstruct an AuditSummary from its ``to_dict`` payload.

        ``top_files`` round-trips as a list of [path, count] pairs (JSON
        doesn't carry tuples natively); we coerce back into the (str, int)
        tuple shape this dataclass declares.
        """
        return cls(
            total_findings=int(data["total_findings"]),
            severity_histogram=dict(data.get("severity_histogram") or {}),
            findings_per_pillar=dict(data.get("findings_per_pillar") or {}),
            top_files=[
                (str(p), int(c)) for p, c in (data.get("top_files") or [])
            ],
            pillars_run=tuple(data.get("pillars_run") or ()),
            pillars_unavailable=tuple(data.get("pillars_unavailable") or ()),
            pillars_errored=tuple(data.get("pillars_errored") or ()),
        )

    @classmethod
    def from_pillar_results(
        cls, results: list[PillarResult], top_n_files: int = 20
    ) -> "AuditSummary":
        all_findings = [f for r in results for f in r.findings]
        severity = Counter(f.severity.value for f in all_findings)
        per_pillar = {r.pillar_name: r.finding_count for r in results}
        file_counter: Counter[str] = Counter()
        for f in all_findings:
            file_counter[f.path] += 1
        pillars_run = tuple(r.pillar_name for r in results if r.status == "ok")
        pillars_unavail = tuple(r.pillar_name for r in results if r.status == "unavailable")
        pillars_err = tuple(r.pillar_name for r in results if r.status == "error")
        return cls(
            total_findings=len(all_findings),
            severity_histogram=dict(severity),
            findings_per_pillar=per_pillar,
            top_files=file_counter.most_common(top_n_files),
            pillars_run=pillars_run,
            pillars_unavailable=pillars_unavail,
            pillars_errored=pillars_err,
        )


@dataclass
class AuditRecord:
    """One audit run's full artefact — signed, content-addressable.

    As of schema audit/1.1 (Move L, 2026-05-16), an AuditRecord MAY
    carry an optional :class:`PreRegistration` + chosen statistic
    metric + :class:`Verdict`, turning the descriptive record into a
    falsifiable artefact for CI gating. Records written under
    schema audit/1.0 (no pre-registration fields) load cleanly under
    the v1.1 codec — the optional fields default to None.
    """

    target_path: str
    target_content_hash: str
    pillars: list[PillarResult]
    summary: AuditSummary
    ophamin_version: str = ""
    ophamin_git_commit: str = ""
    captured_at: str = field(default_factory=_now_utc_iso)
    schema_version: str = SCHEMA_VERSION
    signature: str = ""
    # optional knobs for downstream tooling
    reproduction_command: str = ""
    # Move L additions (optional; absent in schema audit/1.0)
    pre_registration: Any = None       # ophamin.measuring.proof.PreRegistration | None
    pre_registered_metric: str = ""    # statistic name the threshold applies to
    verdict: Any = None                # ophamin.measuring.proof.Verdict | None

    @classmethod
    def build(
        cls,
        target_path: str | Path,
        results: list[PillarResult],
        *,
        reproduction_command: str = "",
    ) -> "AuditRecord":
        return cls(
            target_path=str(Path(target_path).resolve()),
            target_content_hash=_content_hash_of_target(target_path),
            pillars=list(results),
            summary=AuditSummary.from_pillar_results(results),
            ophamin_version=__version__,
            ophamin_git_commit=_ophamin_git_commit(),
            reproduction_command=reproduction_command,
        )

    def _body(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "schema_version": self.schema_version,
            "identity": {
                "ophamin_version": self.ophamin_version,
                "ophamin_git_commit": self.ophamin_git_commit,
                "captured_at": self.captured_at,
            },
            "target": {
                "target_path": self.target_path,
                "target_content_hash": self.target_content_hash,
            },
            "pillars": [p.to_dict() for p in self.pillars],
            "summary": self.summary.to_dict(),
            "reproduction": {"command": self.reproduction_command},
        }
        # Move L optional fields — present only when attach_pre_registration
        # has stamped them. Excluding them when unset keeps schema 1.0
        # records bit-identical and signatures stable for the legacy path.
        if self.pre_registration is not None:
            body["preregistration"] = self.pre_registration.to_dict()
            body["pre_registered_metric"] = self.pre_registered_metric
        if self.verdict is not None:
            body["verdict"] = self.verdict.to_dict()
        return body

    @property
    def audit_id(self) -> str:
        """Content-addressed identifier — SHA-256 over the body."""
        canonical = json.dumps(self._body(), sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def sign(self, key: bytes) -> "AuditRecord":
        canonical = json.dumps(self._body(), sort_keys=True, default=str)
        self.signature = hmac.new(
            key, canonical.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return self

    def verify_signature(self, key: bytes) -> bool:
        if not self.signature:
            return False
        canonical = json.dumps(self._body(), sort_keys=True, default=str)
        expected = hmac.new(
            key, canonical.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, self.signature)

    def to_dict(self) -> dict[str, Any]:
        body = self._body()
        return {"audit_id": self.audit_id, **body, "signature": self.signature}

    def to_json(self, path: str | None = None, indent: int = 2) -> str:
        text = json.dumps(self.to_dict(), indent=indent, default=str)
        if path:
            Path(path).write_text(text, encoding="utf-8")
        return text

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuditRecord":
        """Reconstruct an AuditRecord from its ``to_dict`` payload.

        Accepts both schema audit/1.0 and audit/1.1 payloads. v1.0
        records have no ``preregistration`` / ``verdict`` fields; v1.1
        records may have one or both. Loud-fails on malformed shapes
        rather than silent partial deserialisation.
        """
        identity = data.get("identity") or {}
        target = data.get("target") or {}
        reproduction = data.get("reproduction") or {}
        record = cls(
            target_path=str(target.get("target_path", "")),
            target_content_hash=str(target.get("target_content_hash", "")),
            pillars=[PillarResult.from_dict(p) for p in data.get("pillars", [])],
            summary=AuditSummary.from_dict(data["summary"]),
            ophamin_version=str(identity.get("ophamin_version", "")),
            ophamin_git_commit=str(identity.get("ophamin_git_commit", "")),
            captured_at=str(identity.get("captured_at", _now_utc_iso())),
            schema_version=str(data.get("schema_version", SCHEMA_VERSION)),
            reproduction_command=str(reproduction.get("command", "")),
        )
        # Move L optional fields — present iff schema audit/1.1 producer
        # stamped them. Lazy import keeps the audit module decoupled
        # from the proof module at load time.
        if "preregistration" in data:
            from ophamin.measuring.proof import PreRegistration
            record.pre_registration = PreRegistration.from_dict(
                data["preregistration"]
            )
            record.pre_registered_metric = str(
                data.get("pre_registered_metric", "")
            )
        if "verdict" in data:
            from ophamin.measuring.proof import Verdict
            record.verdict = Verdict.from_dict(data["verdict"])
        record.signature = str(data.get("signature", ""))
        return record

    def attach_pre_registration(
        self,
        *,
        claim: Any,                # ophamin.measuring.proof.Claim
        observed_value: float,
        metric: str = "total_findings",
        analysis_plan: str = "audit-side pre-registration: gate on a chosen audit statistic",
    ) -> "AuditRecord":
        """Stamp an in-place pre-registration + verdict onto this record.

        Per Move L's full universalization of the pre-registration
        discipline: convert this descriptive audit into a falsifiable
        artefact by attaching a Claim's threshold + a decided Verdict.
        Returns self for chaining; bumps the record's schema_version to
        ``audit/1.1`` if it wasn't already there.

        Sign() must be re-called after attach to refresh the signature
        (the body changed, so the old signature is invalid).
        """
        from ophamin.measuring.proof import (
            PreRegistration,
            Verdict,
            content_hash,
        )

        self.pre_registration = PreRegistration(
            config_hash=content_hash({
                "audit_id_pre_attach": "computed-at-attach-time",
                "metric": metric,
            }),
            data_hash=self.target_content_hash,
            analysis_plan=analysis_plan,
            preregistered_at=self.captured_at,
        )
        self.pre_registered_metric = metric
        self.verdict = Verdict.decide(observed_value, claim.threshold)
        self.schema_version = SCHEMA_VERSION
        return self

    @classmethod
    def from_json(cls, path: str | Path) -> "AuditRecord":
        """Load an AuditRecord from a JSON file written by :meth:`to_json`."""
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def wrap_as_proof(
        self,
        *,
        claim: Any,                  # ophamin.measuring.proof.Claim (lazy import)
        observed_value: float,
        pillar_name: str = "audit",
        statistic_name: str = "total_findings",
        library: str = "ophamin",
        library_version: str = "",
        analysis_plan: str = "wrap-audit-as-proof: pre-register a threshold over an audit statistic for CI gating",
        sign_key: bytes | None = None,
    ) -> Any:
        """Wrap this AuditRecord into a pre-registered EmpiricalProofRecord.

        Per Move I: audits are descriptive by default, but a caller that
        wants CI gating (e.g. ``total_findings <= 50``) can wrap the
        record in a proof record that carries the falsifiable claim +
        threshold. The wrapping is lossless — the audit's forensic detail
        (target path + content hash + per-pillar findings + summary) is
        kept in the proof's reproduction + evidence sections.

        Args:
            claim: an :class:`ophamin.measuring.proof.Claim` whose threshold
                is the gate (e.g. ``Threshold("total_findings", "<=", 50)``).
            observed_value: the statistic to evaluate the claim against
                (typically ``record.summary.total_findings`` or a per-severity
                count).
            pillar_name: PillarEvidence pillar identifier in the wrapped
                proof. Default ``"audit"``.
            statistic_name: PillarEvidence statistic name. Default
                ``"total_findings"``.
            library: PillarEvidence library attribution. Default
                ``"ophamin"`` since the audit aggregation IS Ophamin's
                code.
            library_version: PillarEvidence library version. Default
                empty — caller fills if known.
            analysis_plan: PreRegistration analysis plan. Default explains
                the wrap-shape.
            sign_key: HMAC-SHA256 sign key. If ``None``, the proof is
                returned unsigned (caller's responsibility to sign
                before persisting).

        Returns:
            A signed (or unsigned, if ``sign_key=None``)
            :class:`EmpiricalProofRecord`.
        """
        # Lazy imports keep the audit module decoupled from the proof
        # module at top-level (no circular-import risk; wrap_as_proof
        # is the only place that needs the upward dependency).
        from ophamin import __version__ as _ophamin_version
        from ophamin.measuring.proof import (
            DatasetRef,
            EmpiricalProofRecord,
            PillarEvidence,
            PreRegistration,
            Reproduction,
            Verdict,
            content_hash,
        )

        # PreRegistration's data_hash is the audit's target_content_hash —
        # that's the "data" the audit ran against.
        prereg = PreRegistration(
            config_hash=content_hash({
                "audit_id": self.audit_id,
                "pillar_name": pillar_name,
                "statistic_name": statistic_name,
            }),
            data_hash=self.target_content_hash,
            analysis_plan=analysis_plan,
            preregistered_at=self.captured_at,
        )
        dataset = DatasetRef(
            name=f"audit-target:{self.target_path}",
            content_hash=self.target_content_hash,
            n_records=max(self.summary.total_findings, 1),
            source=self.target_path,
            kind="audit_target_tree",
        )
        evidence = PillarEvidence(
            pillar=pillar_name,
            statistic_name=statistic_name,
            statistic_value=observed_value,
            library=library,
            library_version=library_version or _ophamin_version,
            detail={
                "audit_id": self.audit_id,
                "total_findings": self.summary.total_findings,
                "severity_histogram": dict(self.summary.severity_histogram),
                "pillars_run": list(self.summary.pillars_run),
            },
        )
        verdict = Verdict.decide(observed_value, claim.threshold)
        record = EmpiricalProofRecord(
            claim=claim,
            preregistration=prereg,
            datasets=[dataset],
            substrate_name="ophamin.auditing.AuditRecord",
            substrate_git_commit=self.ophamin_git_commit,
            evidence=[evidence],
            verdict=verdict,
            reproduction=Reproduction(
                command=self.reproduction_command or "ophamin audit <target>"
            ),
            ophamin_version=self.ophamin_version,
            ophamin_git_commit=self.ophamin_git_commit,
            created_at=self.captured_at,
        )
        if sign_key is not None:
            record.sign(sign_key)
        return record

    def to_markdown(self, path: str | None = None) -> str:
        """Render the audit as a human-readable Markdown report."""
        lines: list[str] = []
        lines.append(f"# Ophamin Audit Record\n")
        lines.append(f"**Audit ID:** `{self.audit_id}`  ")
        lines.append(f"**Schema:** v{self.schema_version}  ")
        lines.append(f"**Captured:** {self.captured_at}  \n")

        lines.append("## 1. Identity\n")
        lines.append(f"- Ophamin: `{self.ophamin_version}` @ "
                     f"`{self.ophamin_git_commit or '(no commit)'}`")
        lines.append(f"- Target: `{self.target_path}`")
        lines.append(f"- Target content hash: `{self.target_content_hash[:16]}…`\n")

        lines.append("## 2. Pillars run\n")
        lines.append("| pillar | tool | version | status | findings | wall-time |")
        lines.append("|---|---|---|---|---|---|")
        for p in self.pillars:
            lines.append(
                f"| `{p.pillar_name}` | `{p.tool_name}` | "
                f"{p.tool_version or '—'} | {p.status} | "
                f"{p.finding_count if p.status == 'ok' else '—'} | "
                f"{p.wall_time_s:.2f}s |"
            )
        lines.append("")

        lines.append("## 3. Summary\n")
        s = self.summary
        lines.append(f"- Total findings: **{s.total_findings}**")
        lines.append(f"- Pillars run: {len(s.pillars_run)} "
                     f"({', '.join(s.pillars_run) or '—'})")
        if s.pillars_unavailable:
            lines.append(f"- Pillars unavailable: {len(s.pillars_unavailable)} "
                         f"({', '.join(s.pillars_unavailable)})")
        if s.pillars_errored:
            lines.append(f"- Pillars errored: {len(s.pillars_errored)} "
                         f"({', '.join(s.pillars_errored)})")
        lines.append("\n### Severity histogram\n")
        if s.severity_histogram:
            for sev, count in sorted(
                s.severity_histogram.items(),
                key=lambda kv: -kv[1],
            ):
                lines.append(f"- `{sev}`: {count}")
        else:
            lines.append("- _no findings_")
        lines.append("\n### Findings per pillar\n")
        for pillar, count in sorted(s.findings_per_pillar.items()):
            lines.append(f"- `{pillar}`: {count}")
        if s.top_files:
            lines.append("\n### Top 20 hotspot files\n")
            # NOTE: do NOT name this loop variable `path` — it would shadow the
            # `path` parameter of this method and cause the audit markdown to
            # be written into the LAST hotspot source file instead of the
            # caller-specified output path. Bug surfaced in CI 2026-05-15.
            for hotspot_file, count in s.top_files:
                lines.append(f"- `{hotspot_file}`: {count} findings")

        if self.reproduction_command:
            lines.append(f"\n## 4. Reproduction\n```\n{self.reproduction_command}\n```")

        lines.append(f"\n## 5. Signature\n- `{self.signature or '(not signed)'}`\n")

        body = "\n".join(lines) + "\n"
        if path:
            Path(path).write_text(body, encoding="utf-8")
        return body
