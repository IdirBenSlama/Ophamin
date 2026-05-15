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


SCHEMA_VERSION = "audit/1.0"


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
    """One audit run's full artefact — signed, content-addressable."""

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
        return {
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
