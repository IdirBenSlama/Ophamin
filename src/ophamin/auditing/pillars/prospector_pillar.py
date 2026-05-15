"""ProspectorPillar — wraps ``prospector`` (multi-linter aggregator).

Per ``docs/PLUGIN_CATALOG_2026_05_15.md`` §10. Prospector orchestrates
pylint + mypy + dodgy + frosted + others under one config. Severity
maps from prospector's native message-level field.

Output via ``--output-format=json`` is structured.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from ophamin.auditing.base import AuditPillar, Finding, FindingSeverity, PillarResult


_LEVEL_TO_SEVERITY: dict[str, FindingSeverity] = {
    "error":   FindingSeverity.HIGH,
    "warning": FindingSeverity.MEDIUM,
    "info":    FindingSeverity.LOW,
}


class ProspectorPillar(AuditPillar):
    """``prospector --output-format=json <target>`` wrapped as a pillar."""

    name = "prospector"
    tool_binary = "prospector"

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
        cmd = [
            binary,
            "--output-format=json",
            "--no-autodetect",       # don't auto-pick extras like pep8/pep257
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
                f"prospector timed out after {timeout_s}s: {exc}",
                wall_time_s=time.perf_counter() - t0,
            )
        except FileNotFoundError:
            return self.unavailable_result(target_str)
        wall = time.perf_counter() - t0

        try:
            data = json.loads(result.stdout or "{}")
        except json.JSONDecodeError as exc:
            return self.error_result(
                target_str,
                f"prospector emitted unparseable JSON: {exc}; "
                f"stderr: {(result.stderr or '')[:200]}",
                wall_time_s=wall,
            )

        findings: list[Finding] = []
        for msg in data.get("messages", []) or []:
            level = str(msg.get("severity", "info")).lower()
            location = msg.get("location", {}) or {}
            findings.append(Finding(
                pillar_name="prospector",
                rule_id=str(msg.get("code", "PROSPECTOR")),
                severity=_LEVEL_TO_SEVERITY.get(level, FindingSeverity.INFO),
                message=str(msg.get("message", "")).strip(),
                path=str(location.get("path", target_str)),
                line=int(location.get("line", 0) or 0),
                column=int(location.get("character", 0) or 0),
                extra={"source": str(msg.get("source", ""))},
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
