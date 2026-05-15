"""VulturePillar — wraps ``vulture`` (dead-code detector).

vulture's native output is line-by-line text:
``path:line: unused <kind> '<name>' (<confidence>% confidence)``

Severity mapping by confidence:
   >= 80%  → HIGH
   60-79%  → MEDIUM
   < 60%   → LOW

Install via ``pip install 'ophamin[audit]'``.
"""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path
from typing import Any

from ophamin.auditing.base import AuditPillar, Finding, FindingSeverity, PillarResult


_LINE_RE = re.compile(
    r"^(?P<path>[^:]+):(?P<line>\d+):\s+"
    r"unused\s+(?P<kind>\S+)\s+'(?P<name>[^']+)'\s+"
    r"\((?P<confidence>\d+)%\s+confidence\)"
)


def _severity_for(confidence: int) -> FindingSeverity:
    if confidence >= 80:
        return FindingSeverity.HIGH
    if confidence >= 60:
        return FindingSeverity.MEDIUM
    return FindingSeverity.LOW


class VulturePillar(AuditPillar):
    """`vulture <target>` wrapped as an audit pillar."""

    name = "vulture"
    tool_binary = "vulture"

    def run(self, target_path: str | Path, *, timeout_s: float = 600.0, **_kwargs: Any) -> PillarResult:
        target = str(Path(target_path).resolve())
        if not self.is_available():
            return self.unavailable_result(target)

        binary = self.resolved_binary() or self.tool_binary
        cmd = [binary, target]
        t0 = time.perf_counter()
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            return self.error_result(
                target,
                f"vulture timed out after {timeout_s}s: {exc}",
                wall_time_s=time.perf_counter() - t0,
            )
        except FileNotFoundError:
            return self.unavailable_result(target)
        wall = time.perf_counter() - t0

        # vulture exits 0 on no findings, 3 on findings — both fine
        if result.returncode not in (0, 3):
            return self.error_result(
                target,
                f"vulture failed with exit_code={result.returncode}: "
                f"{(result.stderr or '').strip()[:200]}",
                exit_code=result.returncode,
                wall_time_s=wall,
                raw_stderr_bytes=len(result.stderr or ""),
            )

        findings: list[Finding] = []
        for line in (result.stdout or "").splitlines():
            line = line.strip()
            if not line:
                continue
            m = _LINE_RE.match(line)
            if not m:
                continue
            confidence = int(m.group("confidence"))
            findings.append(
                Finding(
                    pillar_name=self.name,
                    rule_id=f"vulture/{m.group('kind')}",
                    severity=_severity_for(confidence),
                    message=f"unused {m.group('kind')} '{m.group('name')}'",
                    path=m.group("path"),
                    line=int(m.group("line")),
                    extra={"kind": m.group("kind"), "confidence": confidence},
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
