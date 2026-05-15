"""SemgrepPillar — wraps ``semgrep`` (custom-rule SAST).

Per ``docs/PLUGIN_CATALOG_2026_05_15.md`` §10. Semgrep blends regex with
AST patterns; rules are written in YAML. Default ruleset = the bundled
``p/python`` (auto-detect) ruleset, which catches OWASP-style + Python-
idiom violations.

Custom rules can encode Kimera's no-fallback rule, Pattern-P naming
violations, etc. — see ``rules/kimera_no_fallback.yml`` for the starter
set bundled with Ophamin.

JSON output via ``--json`` is structured. Severity mapping follows
Semgrep's native scale (ERROR / WARNING / INFO).
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from ophamin.auditing.base import AuditPillar, Finding, FindingSeverity, PillarResult


_SEVERITY_MAP: dict[str, FindingSeverity] = {
    "ERROR":   FindingSeverity.HIGH,
    "WARNING": FindingSeverity.MEDIUM,
    "INFO":    FindingSeverity.LOW,
}


class SemgrepPillar(AuditPillar):
    """``semgrep --json --config <ruleset> <target>`` wrapped as an audit pillar.

    Default ``config="p/python"`` — Semgrep's bundled Python ruleset.
    Override with ``config="rules/kimera_no_fallback.yml"`` (or any path)
    to enforce Kimera-specific rules.
    """

    name = "semgrep"
    tool_binary = "semgrep"

    def run(
        self,
        target_path: str | Path,
        *,
        timeout_s: float = 600.0,
        config: str = "p/python",
        **_kwargs: Any,
    ) -> PillarResult:
        target = Path(target_path).resolve()
        target_str = str(target)
        if not self.is_available():
            return self.unavailable_result(target_str)

        binary = self.resolved_binary() or self.tool_binary
        cmd = [
            binary, "--json",
            "--config", config,
            "--no-rewrite-rule-ids",
            "--quiet",
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
                f"semgrep timed out after {timeout_s}s: {exc}",
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
                f"semgrep emitted unparseable JSON: {exc}; "
                f"stderr: {(result.stderr or '')[:200]}",
                wall_time_s=wall,
            )

        findings: list[Finding] = []
        for r in data.get("results", []) or []:
            extra = r.get("extra", {}) or {}
            severity_str = str(extra.get("severity", "INFO")).upper()
            findings.append(Finding(
                pillar_name="semgrep",
                rule_id=str(r.get("check_id", "SEMGREP_UNKNOWN")),
                severity=_SEVERITY_MAP.get(severity_str, FindingSeverity.INFO),
                message=str(extra.get("message", "")).strip(),
                path=str(r.get("path", target_str)),
                line=int(r.get("start", {}).get("line", 0) or 0),
                column=int(r.get("start", {}).get("col", 0) or 0),
                extra={
                    "metadata": extra.get("metadata", {}),
                    "fix": extra.get("fix", ""),
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
