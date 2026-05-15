"""DeptryPillar — wraps ``deptry`` (project-root dependency checker).

Per ``docs/PLUGIN_CATALOG_2026_05_15.md`` PR #9. Detects:

  DEP001 — undeclared dependency (imported but not in pyproject)
  DEP002 — unused dependency (declared but never imported)
  DEP003 — transitive dependency imported (should be a direct dependency)
  DEP004 — misplaced dev dependency
  DEP005 — standard-library dependency miscategorized

Project-root scoped: the target_path MUST be a directory containing
``pyproject.toml``. On a target that doesn't satisfy this, returns
``status="errored"`` with a helpful message rather than crashing — keeps
the audit pipeline honest about which pillars actually applied.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from ophamin.auditing.base import AuditPillar, Finding, FindingSeverity, PillarResult


SEVERITY_BY_CODE: dict[str, FindingSeverity] = {
    "DEP001": FindingSeverity.HIGH,      # undeclared — runtime crash risk
    "DEP002": FindingSeverity.MEDIUM,    # unused — bloat, not crash
    "DEP003": FindingSeverity.MEDIUM,    # transitive — fragile
    "DEP004": FindingSeverity.LOW,       # misplaced dev dep
    "DEP005": FindingSeverity.LOW,       # stdlib mis-categorized
}


class DeptryPillar(AuditPillar):
    """``deptry <project-root>`` wrapped as an audit pillar."""

    name = "deptry"
    tool_binary = "deptry"

    def run(
        self,
        target_path: str | Path,
        *,
        timeout_s: float = 600.0,
        **_kwargs: Any,
    ) -> PillarResult:
        target = Path(target_path).resolve()
        target_str = str(target)
        if not self.is_available():
            return self.unavailable_result(target_str)

        # Project-root scope check.
        if not target.is_dir() or not (target / "pyproject.toml").is_file():
            return self.error_result(
                target_str,
                f"deptry requires a project-root directory containing "
                f"pyproject.toml; got {target_str!r} which has no pyproject.toml. "
                f"Pass the project root (e.g. ``ophamin audit /path/to/project``).",
                wall_time_s=0.0,
            )

        binary = self.resolved_binary() or self.tool_binary
        # deptry writes JSON to a path; capture stdout for the human readout
        # and parse the JSON file separately.
        json_path = target / ".deptry_audit.json"
        cmd = [binary, "--json-output", str(json_path), "."]
        t0 = time.perf_counter()
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout_s,
                cwd=target_str,
            )
        except subprocess.TimeoutExpired as exc:
            return self.error_result(
                target_str,
                f"deptry timed out after {timeout_s}s: {exc}",
                wall_time_s=time.perf_counter() - t0,
            )
        except FileNotFoundError:
            return self.unavailable_result(target_str)
        wall = time.perf_counter() - t0

        # deptry exits non-zero when issues are found — that's expected.
        # We treat non-zero exit + missing JSON as the error path.
        if not json_path.exists():
            return self.error_result(
                target_str,
                f"deptry did not write {json_path} (exit={result.returncode}); "
                f"stderr: {(result.stderr or '')[:200]}",
                wall_time_s=wall,
            )
        try:
            entries = json.loads(json_path.read_text(encoding="utf-8") or "[]")
        finally:
            try:
                json_path.unlink()
            except OSError:
                pass

        findings: list[Finding] = []
        for e in entries:
            err = e.get("error", {}) if isinstance(e, dict) else {}
            code = str(err.get("code", "DEP_UNKNOWN"))
            message = str(err.get("message", "")).strip()
            module = str(e.get("module", ""))
            loc = e.get("location", {}) if isinstance(e, dict) else {}
            file_path = str(loc.get("file", "") or "")
            line_v = loc.get("line", 0)
            col_v = loc.get("column", 0)
            line = int(line_v) if isinstance(line_v, (int, float)) else 0
            col = int(col_v) if isinstance(col_v, (int, float)) else 0
            findings.append(Finding(
                pillar_name="deptry",
                rule_id=code,
                severity=SEVERITY_BY_CODE.get(code, FindingSeverity.LOW),
                message=f"{message} (module: {module})" if module else message,
                path=file_path or target_str,
                line=line,
                column=col,
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
