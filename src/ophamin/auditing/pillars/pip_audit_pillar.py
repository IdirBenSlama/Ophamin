"""PipAuditPillar — wraps ``pip-audit`` (dependency-vulnerability scanner).

pip-audit's JSON output (``-f json``) lists vulnerable packages with their
known CVEs / GHSAs. One finding per (package, vulnerability) pair.

Severity mapping: pip-audit doesn't report CVSS by default; we use a
conservative HIGH for all vulnerabilities since exploitable dependencies are
universally must-fix territory. The ``extra`` field carries the CVE / GHSA
ID and fix versions if available.

Install via ``pip install 'ophamin[audit]'``.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from ophamin.auditing.base import AuditPillar, Finding, FindingSeverity, PillarResult


class PipAuditPillar(AuditPillar):
    """`pip-audit -f json` wrapped as an audit pillar.

    Audits the *environment* that's currently active (not a specific path).
    The ``target_path`` parameter is recorded for traceability but does not
    affect the scan.
    """

    name = "pip_audit"
    tool_binary = "pip-audit"

    def run(self, target_path: str | Path, *, timeout_s: float = 600.0, **_kwargs: Any) -> PillarResult:
        target = str(Path(target_path).resolve())
        if not self.is_available():
            return self.unavailable_result(target)

        binary = self.resolved_binary() or self.tool_binary
        cmd = [binary, "-f", "json"]
        t0 = time.perf_counter()
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            return self.error_result(
                target,
                f"pip-audit timed out after {timeout_s}s: {exc}",
                wall_time_s=time.perf_counter() - t0,
            )
        except FileNotFoundError:
            return self.unavailable_result(target)
        wall = time.perf_counter() - t0

        # exit code 1 means "vulnerabilities found"; 0 = clean; anything else = error
        if result.returncode not in (0, 1):
            return self.error_result(
                target,
                f"pip-audit failed with exit_code={result.returncode}: "
                f"{(result.stderr or '').strip()[:200]}",
                exit_code=result.returncode,
                wall_time_s=wall,
                raw_stderr_bytes=len(result.stderr or ""),
            )

        try:
            data = json.loads(result.stdout or "[]")
        except json.JSONDecodeError as exc:
            return self.error_result(
                target,
                f"pip-audit produced non-JSON output: {exc}",
                exit_code=result.returncode,
                wall_time_s=wall,
                raw_stdout_bytes=len(result.stdout or ""),
            )

        # pip-audit JSON shape (recent versions): {"dependencies": [{...}]}
        # older versions: a top-level list of dicts. Handle both.
        if isinstance(data, dict):
            entries = data.get("dependencies") or []
        else:
            entries = data

        findings: list[Finding] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            pkg = entry.get("name", "")
            version = entry.get("version", "")
            for vuln in entry.get("vulns", []) or []:
                if not isinstance(vuln, dict):
                    continue
                vuln_id = vuln.get("id", "")
                fix_versions = vuln.get("fix_versions") or []
                findings.append(
                    Finding(
                        pillar_name=self.name,
                        rule_id=vuln_id or f"pip-audit/{pkg}",
                        severity=FindingSeverity.HIGH,
                        message=(
                            f"{pkg} {version} is affected by {vuln_id or '(unknown vuln)'}"
                            + (f"; fix in {','.join(fix_versions)}" if fix_versions else "")
                        ),
                        path=f"<dependency:{pkg}>",
                        extra={
                            "package": pkg,
                            "installed_version": version,
                            "vuln_id": vuln_id,
                            "fix_versions": fix_versions,
                            "description": vuln.get("description"),
                            "aliases": vuln.get("aliases", []),
                        },
                    )
                )

        return PillarResult(
            pillar_name=self.name,
            tool_name=self.tool_binary,
            tool_version=self.tool_version(),
            status="ok",
            target_path=target,
            findings=tuple(findings),
            raw_stdout_bytes=len(result.stdout or ""),
            raw_stderr_bytes=len(result.stderr or ""),
            exit_code=result.returncode,
            wall_time_s=wall,
        )
