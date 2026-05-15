"""RefurbPillar — wraps ``refurb`` (Python modernization suggestions).

Per ``docs/PLUGIN_CATALOG_2026_05_15.md`` §10. Refurb suggests modern
Python idioms (≥3.10): pattern matching, walrus, str.removeprefix,
list / dict / set comprehensions over loops, etc. Where ruff fixes
canonical style, refurb suggests ARCHITECTURAL modernization.

Output via ``--quiet`` is one line per finding:
   ``<file>:<line>:<col> [FURBnnn]: <message>``

We parse it ourselves since refurb has no JSON output mode.
"""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path
from typing import Any

from ophamin.auditing.base import AuditPillar, Finding, FindingSeverity, PillarResult


# Line shape: "<path>:<line>:<col> [FURBnnn]: <message>"
_LINE_RE = re.compile(
    r"^(?P<path>[^:]+):(?P<line>\d+):(?P<col>\d+)\s+\[(?P<rule>FURB\d+)\]:\s+(?P<msg>.+)$"
)


class RefurbPillar(AuditPillar):
    """``refurb <target>`` wrapped as an audit pillar."""

    name = "refurb"
    tool_binary = "refurb"

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

        binary = self.resolved_binary() or self.tool_binary
        cmd = [binary, "--quiet", target_str]
        t0 = time.perf_counter()
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            return self.error_result(
                target_str,
                f"refurb timed out after {timeout_s}s: {exc}",
                wall_time_s=time.perf_counter() - t0,
            )
        except FileNotFoundError:
            return self.unavailable_result(target_str)
        wall = time.perf_counter() - t0

        # Refurb exits non-zero when findings exist — that's expected.
        findings: list[Finding] = []
        for line in (result.stdout or "").splitlines():
            line = line.strip()
            if not line:
                continue
            m = _LINE_RE.match(line)
            if not m:
                continue
            findings.append(Finding(
                pillar_name="refurb",
                rule_id=m.group("rule"),
                # All refurb suggestions are LOW — they're modernization
                # nudges, not bugs.
                severity=FindingSeverity.LOW,
                message=m.group("msg"),
                path=m.group("path"),
                line=int(m.group("line")),
                column=int(m.group("col")),
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
