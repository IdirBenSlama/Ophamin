"""InterrogatePillar — wraps ``interrogate`` (docstring coverage).

Per ``docs/PLUGIN_CATALOG_2026_05_15.md`` PR #9 sibling. Surfaces per-file
docstring coverage % and emits one Finding per file whose coverage is below
a threshold (default 80%).

File-scope (works on any directory). Uses the ``interrogate`` Python API
directly — no subprocess overhead, no text-format parsing.

Severity mapping by per-file coverage:

  perc < 30%  → HIGH   (badly under-documented; obvious target for fix)
  perc < 60%  → MEDIUM
  perc < 80%  → LOW    (still flagged, but mild)
  perc >= 80% → not flagged (above default fail-under threshold)
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from ophamin.auditing.base import AuditPillar, Finding, FindingSeverity, PillarResult


#: severity bands keyed on docstring coverage percentage
_HIGH_THRESHOLD = 30.0
_MEDIUM_THRESHOLD = 60.0
_LOW_THRESHOLD = 80.0


class InterrogatePillar(AuditPillar):
    """``interrogate`` (docstring coverage) wrapped as an audit pillar.

    Unlike the other pillars, this one uses the library's Python API rather
    than spawning a subprocess — interrogate is pure-Python and importable.
    """

    name = "interrogate"
    tool_binary = "interrogate"

    def run(
        self,
        target_path: str | Path,
        *,
        timeout_s: float = 600.0,
        fail_under: float = _LOW_THRESHOLD,
        **_kwargs: Any,
    ) -> PillarResult:
        target = Path(target_path).resolve()
        target_str = str(target)
        if not self.is_available():
            return self.unavailable_result(target_str)

        try:
            from interrogate import coverage as ic_coverage
        except ImportError:
            return self.unavailable_result(target_str)

        if not target.exists():
            return self.error_result(
                target_str,
                f"interrogate target does not exist: {target_str}",
                wall_time_s=0.0,
            )

        t0 = time.perf_counter()
        try:
            results = ic_coverage.InterrogateCoverage(
                paths=[target_str],
            ).get_coverage()
        except Exception as exc:
            return self.error_result(
                target_str,
                f"interrogate raised {type(exc).__name__}: {exc}",
                wall_time_s=time.perf_counter() - t0,
            )
        wall = time.perf_counter() - t0

        # Per-file findings — one Finding per file below ``fail_under``.
        findings: list[Finding] = []
        for fr in results.file_results:
            perc = float(fr.perc_covered)
            if perc >= fail_under:
                continue
            if perc < _HIGH_THRESHOLD:
                severity = FindingSeverity.HIGH
            elif perc < _MEDIUM_THRESHOLD:
                severity = FindingSeverity.MEDIUM
            else:
                severity = FindingSeverity.LOW
            findings.append(Finding(
                pillar_name="interrogate",
                rule_id="INTERROGATE_LOW",
                severity=severity,
                message=(
                    f"docstring coverage {perc:.1f}% "
                    f"({fr.covered}/{fr.total} documented; "
                    f"{fr.missing} missing) — below {fail_under:.0f}%"
                ),
                path=str(fr.filename),
                line=0,
                column=0,
                extra={
                    "perc_covered": perc,
                    "total": int(fr.total),
                    "covered": int(fr.covered),
                    "missing": int(fr.missing),
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
