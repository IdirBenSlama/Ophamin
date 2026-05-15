"""RadonPillar — wraps ``radon cc`` (cyclomatic complexity).

radon's ``cc`` subcommand emits JSON via ``-j``. Each entry carries a
``rank`` (A-F, A=best) and a numeric ``complexity``. We map:

   A    → INFO   (1–5)
   B    → LOW    (6–10)
   C    → MEDIUM (11–20)
   D    → HIGH   (21–30)
   E    → HIGH   (31–40)
   F    → CRITICAL (41+)

A "finding" here is one function/method/class with rank ≥ B (i.e. CC ≥ 6).
Below-threshold complexity is silently not a finding.

Install via ``pip install 'ophamin[audit]'``.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from ophamin.auditing.base import AuditPillar, Finding, FindingSeverity, PillarResult


RANK_SEVERITY_MAP = {
    "A": FindingSeverity.INFO,
    "B": FindingSeverity.LOW,
    "C": FindingSeverity.MEDIUM,
    "D": FindingSeverity.HIGH,
    "E": FindingSeverity.HIGH,
    "F": FindingSeverity.CRITICAL,
}


class RadonPillar(AuditPillar):
    """`radon cc -j <target>` wrapped as an audit pillar.

    Threshold for what counts as a finding: rank >= B (CC >= 6). Below that,
    the code is considered "easy" and not flagged.
    """

    name = "radon"
    tool_binary = "radon"

    def run(
        self,
        target_path: str | Path,
        *,
        timeout_s: float = 600.0,
        min_rank: str = "B",
        **_kwargs: Any,
    ) -> PillarResult:
        target = str(Path(target_path).resolve())
        if not self.is_available():
            return self.unavailable_result(target)

        binary = self.resolved_binary() or self.tool_binary
        cmd = [binary, "cc", "-j", "-n", min_rank, target]
        t0 = time.perf_counter()
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            return self.error_result(
                target,
                f"radon timed out after {timeout_s}s: {exc}",
                wall_time_s=time.perf_counter() - t0,
            )
        except FileNotFoundError:
            return self.unavailable_result(target)
        wall = time.perf_counter() - t0

        if result.returncode != 0:
            return self.error_result(
                target,
                f"radon failed with exit_code={result.returncode}: "
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
                f"radon produced non-JSON output: {exc}",
                exit_code=result.returncode,
                wall_time_s=wall,
                raw_stdout_bytes=len(result.stdout or ""),
            )

        findings: list[Finding] = []
        for file_path, entries in data.items():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                rank = str(entry.get("rank", "A")).upper()
                complexity = int(entry.get("complexity", 0))
                findings.append(
                    Finding(
                        pillar_name=self.name,
                        rule_id=f"radon/cc/rank-{rank}",
                        severity=RANK_SEVERITY_MAP.get(rank, FindingSeverity.LOW),
                        message=(
                            f"{entry.get('type', 'function')} "
                            f"'{entry.get('name', '')}' has cyclomatic "
                            f"complexity {complexity} (rank {rank})"
                        ),
                        path=file_path,
                        line=int(entry.get("lineno", 0) or 0),
                        column=int(entry.get("col_offset", 0) or 0),
                        extra={
                            "type": entry.get("type"),
                            "name": entry.get("name"),
                            "complexity": complexity,
                            "rank": rank,
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
