"""BanditPillar — wraps ``bandit`` (security linter).

bandit emits JSON via ``-f json``. Each result carries ``issue_severity``
(LOW/MEDIUM/HIGH) and ``issue_confidence``. We map ``issue_severity`` to our
normalised scale directly; ``issue_confidence`` is preserved in ``extra``.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from ophamin.auditing.base import AuditPillar, Finding, FindingSeverity, PillarResult


BANDIT_SEVERITY_MAP = {
    "HIGH": FindingSeverity.HIGH,
    "MEDIUM": FindingSeverity.MEDIUM,
    "LOW": FindingSeverity.LOW,
}


class BanditPillar(AuditPillar):
    """`bandit -r -f json <target>` wrapped as an audit pillar."""

    name = "bandit"
    tool_binary = "bandit"

    def run(self, target_path: str | Path, *, timeout_s: float = 600.0, **_kwargs: Any) -> PillarResult:
        target = str(Path(target_path).resolve())
        if not self.is_available():
            return self.unavailable_result(target)

        binary = self.resolved_binary() or self.tool_binary
        cmd = [
            binary, "-r", target,
            "-f", "json",
            "--quiet",                  # suppress progress bar
        ]
        t0 = time.perf_counter()
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            return self.error_result(
                target,
                f"bandit timed out after {timeout_s}s: {exc}",
                wall_time_s=time.perf_counter() - t0,
            )
        except FileNotFoundError:
            return self.unavailable_result(target)
        wall = time.perf_counter() - t0

        # bandit's exit code is 0 on no findings, 1 on findings — both produce
        # valid JSON. Non-zero exit + empty stdout = real error.
        if not result.stdout and result.returncode not in (0, 1):
            return self.error_result(
                target,
                f"bandit failed with exit_code={result.returncode}: "
                f"{(result.stderr or '').strip()[:200]}",
                exit_code=result.returncode,
                wall_time_s=wall,
                raw_stderr_bytes=len(result.stderr or ""),
            )

        try:
            data = json.loads(result.stdout or "{}")
        except json.JSONDecodeError as exc:
            return self.error_result(
                target,
                f"bandit produced non-JSON output: {exc}",
                exit_code=result.returncode,
                wall_time_s=wall,
                raw_stdout_bytes=len(result.stdout or ""),
                raw_stderr_bytes=len(result.stderr or ""),
            )

        findings: list[Finding] = []
        for entry in data.get("results", []) or []:
            if not isinstance(entry, dict):
                continue
            issue_sev = str(entry.get("issue_severity", "LOW")).upper()
            findings.append(
                Finding(
                    pillar_name=self.name,
                    rule_id=str(entry.get("test_id", "") or ""),
                    severity=BANDIT_SEVERITY_MAP.get(issue_sev, FindingSeverity.LOW),
                    message=str(entry.get("issue_text", "")),
                    path=str(entry.get("filename", "")),
                    line=int(entry.get("line_number", 0) or 0),
                    column=int(entry.get("col_offset", 0) or 0),
                    extra={
                        "test_name": entry.get("test_name"),
                        "issue_confidence": entry.get("issue_confidence"),
                        "issue_cwe": entry.get("issue_cwe"),
                        "more_info": entry.get("more_info"),
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
