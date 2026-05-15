"""CoveragePillar — wraps ``coverage.py`` (line + branch coverage).

Project-scope (needs a test suite + a target package). Runs
``coverage run -m pytest`` then ``coverage json`` to harvest per-file
coverage metrics, then emits one Finding per file whose coverage is
below ``min_coverage`` (default 70%).

Severity mapping (per-file line coverage %):

  < 30%  → HIGH   (mostly untested)
  < 50%  → MEDIUM
  < 70%  → LOW    (default fail-under)
  ≥ 70%  → not flagged
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from ophamin.auditing.base import AuditPillar, Finding, FindingSeverity, PillarResult


class CoveragePillar(AuditPillar):
    """``coverage run -m pytest && coverage json`` wrapped as an audit pillar.

    Project-scope. Target should be a directory containing both source
    code AND a test suite the pytest runner can discover. Output is
    ``coverage.json`` (default name from coverage.py).
    """

    name = "coverage"
    tool_binary = "coverage"

    def run(
        self,
        target_path: str | Path,
        *,
        timeout_s: float = 600.0,
        min_coverage: float = 70.0,
        pytest_args: tuple[str, ...] = ("-q",),
        **_kwargs: Any,
    ) -> PillarResult:
        target = Path(target_path).resolve()
        target_str = str(target)
        if not self.is_available():
            return self.unavailable_result(target_str)

        if not target.is_dir():
            return self.error_result(
                target_str,
                f"coverage target must be a directory; got {target_str!r}",
                wall_time_s=0.0,
            )

        binary = self.resolved_binary() or self.tool_binary
        json_path = target / ".coverage_audit.json"
        # Run pytest under coverage. Source restricted to target so we
        # don't measure coverage of dep packages.
        run_cmd = [
            binary, "run", f"--source={target_str}",
            "-m", "pytest", *pytest_args,
        ]
        report_cmd = [binary, "json", f"-o", str(json_path), "--quiet"]
        t0 = time.perf_counter()
        try:
            run_result = subprocess.run(
                run_cmd, capture_output=True, text=True, timeout=timeout_s,
                cwd=target_str,
            )
        except subprocess.TimeoutExpired as exc:
            return self.error_result(
                target_str,
                f"coverage run -m pytest timed out after {timeout_s}s: {exc}",
                wall_time_s=time.perf_counter() - t0,
            )
        except FileNotFoundError:
            return self.unavailable_result(target_str)
        # pytest exit non-zero on failures is fine — coverage was collected.
        try:
            report_result = subprocess.run(
                report_cmd, capture_output=True, text=True, timeout=60,
                cwd=target_str,
            )
        except subprocess.TimeoutExpired as exc:
            return self.error_result(
                target_str,
                f"coverage json export timed out: {exc}",
                wall_time_s=time.perf_counter() - t0,
            )
        wall = time.perf_counter() - t0

        if not json_path.exists():
            return self.error_result(
                target_str,
                f"coverage did not write {json_path}; "
                f"run stderr: {(run_result.stderr or '')[:200]}",
                wall_time_s=wall,
            )
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        finally:
            try:
                json_path.unlink()
            except OSError:
                pass

        findings: list[Finding] = []
        for file_path, file_data in (data.get("files", {}) or {}).items():
            summary = file_data.get("summary", {}) or {}
            perc = float(summary.get("percent_covered", 0.0))
            if perc >= min_coverage:
                continue
            if perc < 30.0:
                severity = FindingSeverity.HIGH
            elif perc < 50.0:
                severity = FindingSeverity.MEDIUM
            else:
                severity = FindingSeverity.LOW
            findings.append(Finding(
                pillar_name="coverage",
                rule_id="COV_LOW",
                severity=severity,
                message=(
                    f"line coverage {perc:.1f}% — below {min_coverage:.0f}%"
                ),
                path=str(file_path),
                line=0,
                extra={
                    "percent_covered": perc,
                    "covered_lines": int(summary.get("covered_lines", 0)),
                    "missing_lines": int(summary.get("missing_lines", 0)),
                    "num_statements": int(summary.get("num_statements", 0)),
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
