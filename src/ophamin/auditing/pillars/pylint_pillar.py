"""PylintPillar — wraps ``pylint`` (deeper Python static analysis).

Per ``docs/PLUGIN_CATALOG_2026_05_15.md`` §10. Pylint covers checks ruff
can't replicate (deep type inference, custom plugin support, complex
inheritance analysis). It's slow; run it as a deeper-bench pillar
opt-in alongside the fast file-scope set.

Pylint output via ``--output-format=json`` is structured + stable.

Severity mapping (pylint's message types):
  E* error      → HIGH
  W* warning    → MEDIUM
  C* convention → LOW
  R* refactor   → LOW
  I* info       → INFO
  F* fatal      → CRITICAL (config / parse error — pillar usually errors out)
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from ophamin.auditing.base import AuditPillar, Finding, FindingSeverity, PillarResult


_TYPE_TO_SEVERITY: dict[str, FindingSeverity] = {
    "error":      FindingSeverity.HIGH,
    "warning":    FindingSeverity.MEDIUM,
    "convention": FindingSeverity.LOW,
    "refactor":   FindingSeverity.LOW,
    "info":       FindingSeverity.INFO,
    "fatal":      FindingSeverity.CRITICAL,
}


class PylintPillar(AuditPillar):
    """``pylint --output-format=json <target>`` wrapped as an audit pillar."""

    name = "pylint"
    tool_binary = "pylint"

    def run(
        self,
        target_path: str | Path,
        *,
        timeout_s: float = 1200.0,
        **_kwargs: Any,
    ) -> PillarResult:
        target = Path(target_path).resolve()
        target_str = str(target)
        if not self.is_available():
            return self.unavailable_result(target_str)

        binary = self.resolved_binary() or self.tool_binary
        # ``--output-format=json`` emits a JSON array of findings.
        # ``--exit-zero`` so a non-zero exit (which pylint defaults to on
        # any finding) doesn't raise a CalledProcessError before we read
        # the JSON.
        cmd = [
            binary,
            "--output-format=json",
            "--exit-zero",
            "--score=no",
            "--reports=no",
            target_str,
        ]
        t0 = time.perf_counter()
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            return self.error_result(
                target_str,
                f"pylint timed out after {timeout_s}s: {exc}",
                wall_time_s=time.perf_counter() - t0,
            )
        except FileNotFoundError:
            return self.unavailable_result(target_str)
        wall = time.perf_counter() - t0

        try:
            entries = json.loads(result.stdout or "[]")
        except json.JSONDecodeError as exc:
            return self.error_result(
                target_str,
                f"pylint emitted unparseable JSON: {exc}; "
                f"stderr: {(result.stderr or '')[:200]}",
                wall_time_s=wall,
            )

        findings: list[Finding] = []
        for e in entries:
            if not isinstance(e, dict):
                continue
            msg_type = str(e.get("type", "info")).lower()
            severity = _TYPE_TO_SEVERITY.get(msg_type, FindingSeverity.INFO)
            findings.append(Finding(
                pillar_name="pylint",
                rule_id=str(e.get("message-id") or e.get("symbol") or "PYLINT"),
                severity=severity,
                message=str(e.get("message", "")),
                path=str(e.get("path", target_str)),
                line=int(e.get("line", 0) or 0),
                column=int(e.get("column", 0) or 0),
                extra={
                    "symbol": str(e.get("symbol", "")),
                    "module": str(e.get("module", "")),
                    "obj": str(e.get("obj", "")),
                },
            ))

        return PillarResult(
            pillar_name=self.name,
            tool_name=self.tool_binary,
            tool_version=self.tool_version(),
            status="ok",
            target_path=target_str,
            findings=tuple(findings),
            wall_time_s=wall,
        )
