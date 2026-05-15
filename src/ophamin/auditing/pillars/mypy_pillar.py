"""MypyPillar — wraps ``mypy`` (static type-checker).

mypy's native output is line-by-line text in the form
``path:line:col: severity: message  [error-code]``. We parse that directly
since mypy's JSON output is non-standard and version-dependent.

Severity mapping:
  error        → HIGH
  warning      → MEDIUM
  note         → INFO
  (anything else) → LOW
"""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path
from typing import Any

from ophamin.auditing.base import AuditPillar, Finding, FindingSeverity, PillarResult


MYPY_SEVERITY_MAP = {
    "error": FindingSeverity.HIGH,
    "warning": FindingSeverity.MEDIUM,
    "note": FindingSeverity.INFO,
}

# Matches: path:line[:col]: severity: message [optional error-code]
# e.g. "src/foo.py:42:10: error: Incompatible return value type  [return-value]"
_LINE_RE = re.compile(
    r"^(?P<path>[^:]+):(?P<line>\d+)(?::(?P<col>\d+))?: "
    r"(?P<severity>\w+): (?P<message>.+?)"
    r"(?:\s+\[(?P<code>[\w-]+)\])?$"
)


class MypyPillar(AuditPillar):
    """`mypy --no-error-summary --show-error-codes <target>` wrapped as an audit pillar."""

    name = "mypy"
    tool_binary = "mypy"

    def run(self, target_path: str | Path, *, timeout_s: float = 1200.0, **_kwargs: Any) -> PillarResult:
        target = str(Path(target_path).resolve())
        if not self.is_available():
            return self.unavailable_result(target)

        binary = self.resolved_binary() or self.tool_binary
        cmd = [
            binary,
            "--no-error-summary",
            "--show-error-codes",
            "--show-column-numbers",
            "--no-color-output",
            "--no-incremental",          # honest run, no cached state
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
                f"mypy timed out after {timeout_s}s: {exc}",
                wall_time_s=time.perf_counter() - t0,
            )
        except FileNotFoundError:
            return self.unavailable_result(target)
        wall = time.perf_counter() - t0

        findings: list[Finding] = []
        for line in (result.stdout or "").splitlines():
            line = line.strip()
            if not line:
                continue
            m = _LINE_RE.match(line)
            if not m:
                # tolerate prefixes like "Success:" or "Found N errors..." —
                # those aren't findings, they're status lines
                continue
            sev = m.group("severity").lower()
            findings.append(
                Finding(
                    pillar_name=self.name,
                    rule_id=m.group("code") or "",
                    severity=MYPY_SEVERITY_MAP.get(sev, FindingSeverity.LOW),
                    message=m.group("message"),
                    path=m.group("path"),
                    line=int(m.group("line")),
                    column=int(m.group("col") or 0),
                ),
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
