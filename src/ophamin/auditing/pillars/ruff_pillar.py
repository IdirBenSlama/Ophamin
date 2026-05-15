"""RuffPillar — wraps ``ruff check`` (fast Python linter).

ruff covers what flake8, pylint, isort, pyupgrade, autoflake, eradicate etc.
used to cover, with ~100× the speed. JSON output is stable and well-documented.

Severity mapping: ruff doesn't ship a uniform severity model (each rule
chooses its own); we map by rule prefix:
  E*, F*    → HIGH    (errors)
  W*        → MEDIUM  (warnings)
  C*        → MEDIUM  (complexity)
  S*        → HIGH    (security / bandit-equivalent)
  B*        → MEDIUM  (bugbear)
  RUF*      → MEDIUM  (ruff-native)
  everything else → LOW
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from ophamin.auditing.base import AuditPillar, Finding, FindingSeverity, PillarResult


SEVERITY_PREFIX_MAP = {
    "E": FindingSeverity.HIGH,
    "F": FindingSeverity.HIGH,
    "S": FindingSeverity.HIGH,
    "W": FindingSeverity.MEDIUM,
    "C": FindingSeverity.MEDIUM,
    "B": FindingSeverity.MEDIUM,
    "RUF": FindingSeverity.MEDIUM,
}


def _severity_for(rule_id: str) -> FindingSeverity:
    if not rule_id:
        return FindingSeverity.LOW
    # match longest prefix first, since "RUF" must outrank "R"
    for prefix in sorted(SEVERITY_PREFIX_MAP, key=len, reverse=True):
        if rule_id.startswith(prefix):
            return SEVERITY_PREFIX_MAP[prefix]
    return FindingSeverity.LOW


class RuffPillar(AuditPillar):
    """`ruff check --output-format=json <target>` wrapped as an audit pillar."""

    name = "ruff"
    tool_binary = "ruff"

    def run(self, target_path: str | Path, *, timeout_s: float = 600.0, **_kwargs: Any) -> PillarResult:
        target = str(Path(target_path).resolve())
        if not self.is_available():
            return self.unavailable_result(target)

        binary = self.resolved_binary() or self.tool_binary
        cmd = [
            binary, "check",
            "--output-format=json",
            "--no-cache",          # honest run
            "--exit-zero",         # don't fail the subprocess on findings
            target,
        ]
        t0 = time.perf_counter()
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            return self.error_result(
                target,
                f"ruff timed out after {timeout_s}s: {exc}",
                wall_time_s=time.perf_counter() - t0,
            )
        except FileNotFoundError:
            return self.unavailable_result(target)
        wall = time.perf_counter() - t0

        try:
            entries = json.loads(result.stdout or "[]")
        except json.JSONDecodeError as exc:
            return self.error_result(
                target,
                f"ruff produced non-JSON output: {exc}",
                exit_code=result.returncode,
                wall_time_s=wall,
                raw_stdout_bytes=len(result.stdout or ""),
                raw_stderr_bytes=len(result.stderr or ""),
            )

        findings: list[Finding] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            rule_id = str(entry.get("code", "") or "")
            location = entry.get("location") or {}
            findings.append(
                Finding(
                    pillar_name=self.name,
                    rule_id=rule_id,
                    severity=_severity_for(rule_id),
                    message=str(entry.get("message", "")),
                    path=str(entry.get("filename", "")),
                    line=int(location.get("row", 0) or 0),
                    column=int(location.get("column", 0) or 0),
                    extra={
                        "url": entry.get("url"),
                        "fix": entry.get("fix"),
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
