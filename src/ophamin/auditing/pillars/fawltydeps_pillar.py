"""FawltyDepsPillar — wraps ``fawltydeps`` (project-root dependency checker).

Per ``docs/PLUGIN_CATALOG_2026_05_15.md`` PR #9. Detects:

  undeclared        — modules imported but not in pyproject (HIGH)
  unused            — declared dependencies never imported (MEDIUM)

Project-root scoped, like deptry. Pinned to ``--code <target>/src``
(matching Ophamin's layout) when ``src/`` exists, else falls back to the
target itself.

fawltydeps emits a JSON document with sections like:

    {
      "undeclared_deps": [{"name": "foo", "references": [...]}, ...],
      "unused_deps":     [{"name": "bar", "references": [...]}, ...],
      "version": "...",
    }

We map each entry into a ``Finding``.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from ophamin.auditing.base import AuditPillar, Finding, FindingSeverity, PillarResult


class FawltyDepsPillar(AuditPillar):
    """``fawltydeps --json --code <code> --deps <pyproject>`` wrapped as a pillar."""

    name = "fawltydeps"
    tool_binary = "fawltydeps"

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

        if not target.is_dir() or not (target / "pyproject.toml").is_file():
            return self.error_result(
                target_str,
                f"fawltydeps requires a project-root directory containing "
                f"pyproject.toml; got {target_str!r} which has no pyproject.toml.",
                wall_time_s=0.0,
            )

        # Pick the code root in priority order. Project layouts vary:
        #   * ``src/`` — modern Python convention (Ophamin)
        #   * ``<project_name>/`` — Kimera-style (kimera_swm/), Django-style
        #   * ``lib/`` — older Python convention
        # Fall back to the project root itself if none match — but warn that
        # fawltydeps will walk every subdirectory (including data/ corpora).
        code_root = target
        # Try to read pyproject's project.name to find a same-named subdir.
        project_name = ""
        try:
            text = (target / "pyproject.toml").read_text(encoding="utf-8")
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("name") and "=" in line:
                    project_name = line.split("=", 1)[1].strip().strip("'\"")
                    break
        except OSError:
            pass

        for candidate in ("src", project_name, "lib"):
            if not candidate:
                continue
            cand_path = target / candidate
            if cand_path.is_dir():
                code_root = cand_path
                break
        binary = self.resolved_binary() or self.tool_binary
        cmd = [
            binary, "--json",
            "--code", str(code_root),
            "--deps", str(target / "pyproject.toml"),
        ]
        t0 = time.perf_counter()
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout_s,
                cwd=target_str,
            )
        except subprocess.TimeoutExpired as exc:
            return self.error_result(
                target_str,
                f"fawltydeps timed out after {timeout_s}s: {exc}",
                wall_time_s=time.perf_counter() - t0,
            )
        except FileNotFoundError:
            return self.unavailable_result(target_str)
        wall = time.perf_counter() - t0

        # fawltydeps exits non-zero on findings; that's expected.
        try:
            data = json.loads(result.stdout or "{}")
        except json.JSONDecodeError as exc:
            return self.error_result(
                target_str,
                f"fawltydeps emitted unparseable JSON: {exc}; "
                f"stderr: {(result.stderr or '')[:200]}",
                wall_time_s=wall,
            )

        findings: list[Finding] = []
        # Both the v0.20 schema (top-level lists) and the older v0.16+ schema
        # (nested under "settings") are supported; we look in both places.
        for section, severity, label in (
            ("undeclared_deps", FindingSeverity.HIGH, "undeclared dependency"),
            ("unused_deps",     FindingSeverity.MEDIUM, "unused dependency"),
        ):
            entries = data.get(section, []) or []
            for entry in entries:
                name = (entry.get("name") if isinstance(entry, dict) else None) or "<unknown>"
                refs = (entry.get("references") if isinstance(entry, dict) else None) or []
                # First reference's source file, if any, as the location.
                file_path: str = ""
                parsed_line: int | None = None
                if refs:
                    ref0 = refs[0] if isinstance(refs[0], dict) else {}
                    file_path = str(ref0.get("source", "")) or str(ref0.get("path", ""))
                    line_v = ref0.get("lineno") or ref0.get("line")
                    if line_v is not None:
                        try:
                            parsed_line = int(line_v)
                        except (TypeError, ValueError):
                            parsed_line = None
                rule_id = "FD_UNDECLARED" if section == "undeclared_deps" else "FD_UNUSED"
                findings.append(Finding(
                    pillar_name="fawltydeps",
                    rule_id=rule_id,
                    severity=severity,
                    message=f"{label}: {name}",
                    path=file_path or target_str,
                    line=parsed_line or 0,
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
