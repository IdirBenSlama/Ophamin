"""PipAuditPillar — wraps ``pip-audit`` (dependency-vulnerability scanner).

pip-audit's JSON output (``-f json``) lists vulnerable packages with their
known CVEs / GHSAs. One finding per (package, vulnerability) pair.

Severity mapping: pip-audit doesn't report CVSS by default; we use a
conservative HIGH for all vulnerabilities since exploitable dependencies are
universally must-fix territory. The ``extra`` field carries the CVE / GHSA
ID and fix versions if available.

**Scoping** (added 2026-05-15 after methodology gap surfaced in EMPIRICAL_VALIDATION
Family S): pass ``python_exe=<path>`` to scope the scan to a specific venv (e.g.
the audit-target's venv rather than Ophamin's ambient venv). Without it, the
pillar inspects whatever Python pip-audit picks up — typically the venv that
launched Ophamin.

**Risk-accepted CVEs** (added 2026-05-15): pass ``ignore_vulns=("CVE-X", ...)``
to suppress specific CVEs that have been reviewed and risk-accepted (e.g.
unfixable transitive deps with no exploitable path in Ophamin's runtime). The
canonical Ophamin risk-acceptance list lives in
``docs/RISK_ACCEPTED_CVES.md``; the default ``ignore_vulns`` parameter is
populated from that list.

Install via ``pip install 'ophamin[audit]'``.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from ophamin.auditing.base import AuditPillar, Finding, FindingSeverity, PillarResult


# Risk-accepted CVEs — see docs/RISK_ACCEPTED_CVES.md for per-CVE rationale.
# Each entry must have a matching section in the docs file. Treat additions to
# this list as a security-review requirement.
DEFAULT_RISK_ACCEPTED_CVES: tuple[str, ...] = (
    # diskcache 5.6.3: unsafe pickle deserialization. Local-only attack
    # surface (cache files written and read by Ophamin itself). No upstream
    # fix; diskcache 5.6.3 is latest. Pulled in transitively by dvc-data.
    "CVE-2025-69872",
    # py 1.11.0: ReDoS in SVN status parsing. Ophamin does not use SVN.
    # Zero reachable attack surface. Project abandoned; py 1.11.0 is latest.
    # Pulled in transitively by interrogate.
    "PYSEC-2022-42969",
)


class PipAuditPillar(AuditPillar):
    """`pip-audit -f json` wrapped as an audit pillar.

    Audits the *environment* that's currently active by default. Pass
    ``python_exe`` (via constructor or per-call kwarg) to scope to a specific
    venv. The ``target_path`` parameter is recorded for traceability.
    """

    name = "pip_audit"
    tool_binary = "pip-audit"

    def __init__(
        self,
        *,
        python_exe: str | Path | None = None,
        ignore_vulns: tuple[str, ...] | None = None,
    ) -> None:
        super().__init__()
        self.python_exe = Path(python_exe).expanduser() if python_exe else None
        # ``None`` means "use the curated default risk-acceptance list";
        # ``()`` (empty tuple) means "ignore nothing — surface every CVE".
        self.ignore_vulns: tuple[str, ...] = (
            DEFAULT_RISK_ACCEPTED_CVES if ignore_vulns is None else tuple(ignore_vulns)
        )

    def run(self, target_path: str | Path, *, timeout_s: float = 600.0, **_kwargs: Any) -> PillarResult:
        target = str(Path(target_path).resolve())
        if not self.is_available():
            return self.unavailable_result(target)

        binary = self.resolved_binary() or self.tool_binary
        cmd = [binary, "-f", "json"]
        # Per-call override: caller can override ignore_vulns / python_exe.
        per_call_python: Path | None = _kwargs.get("python_exe")
        python_exe: Path | None
        if per_call_python is not None:
            python_exe = Path(per_call_python).expanduser()
        else:
            python_exe = self.python_exe
        # When auditing a target venv (rather than the ambient one), generate
        # a freeze of its installed packages and feed it to pip-audit via
        # --requirement. This is the canonical pattern; pip-audit's --path is
        # for project paths (not venv site-packages).
        target_venv_freeze: Path | None = None
        if python_exe is not None:
            if not python_exe.exists():
                return self.error_result(
                    target,
                    f"python_exe not found: {python_exe}",
                    wall_time_s=0.0,
                )
            target_venv_freeze = self._dump_freeze(python_exe)
            if target_venv_freeze is None:
                return self.error_result(
                    target,
                    f"could not pip-freeze the target venv: {python_exe}",
                    wall_time_s=0.0,
                )
            cmd.extend(["--requirement", str(target_venv_freeze), "--disable-pip"])
        per_call_ignore = _kwargs.get("ignore_vulns")
        ignore_vulns: tuple[str, ...] = (
            tuple(per_call_ignore) if per_call_ignore is not None
            else self.ignore_vulns
        )
        for vuln_id in ignore_vulns:
            cmd.extend(["--ignore-vuln", vuln_id])
        t0 = time.perf_counter()
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            return self.error_result(
                target,
                f"pip-audit timed out after {timeout_s}s: {exc}",
                wall_time_s=time.perf_counter() - t0,
            )
        except FileNotFoundError:
            return self.unavailable_result(target)
        wall = time.perf_counter() - t0

        # exit code 1 means "vulnerabilities found"; 0 = clean; anything else = error
        if result.returncode not in (0, 1):
            return self.error_result(
                target,
                f"pip-audit failed with exit_code={result.returncode}: "
                f"{(result.stderr or '').strip()[:200]}",
                exit_code=result.returncode,
                wall_time_s=wall,
                raw_stderr_bytes=len(result.stderr or ""),
            )

        try:
            data = json.loads(result.stdout or "[]")
        except json.JSONDecodeError as exc:
            return self.error_result(
                target,
                f"pip-audit produced non-JSON output: {exc}",
                exit_code=result.returncode,
                wall_time_s=wall,
                raw_stdout_bytes=len(result.stdout or ""),
            )

        # pip-audit JSON shape (recent versions): {"dependencies": [{...}]}
        # older versions: a top-level list of dicts. Handle both.
        if isinstance(data, dict):
            entries = data.get("dependencies") or []
        else:
            entries = data

        findings: list[Finding] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            pkg = entry.get("name", "")
            version = entry.get("version", "")
            for vuln in entry.get("vulns", []) or []:
                if not isinstance(vuln, dict):
                    continue
                vuln_id = vuln.get("id", "")
                fix_versions = vuln.get("fix_versions") or []
                findings.append(
                    Finding(
                        pillar_name=self.name,
                        rule_id=vuln_id or f"pip-audit/{pkg}",
                        severity=FindingSeverity.HIGH,
                        message=(
                            f"{pkg} {version} is affected by {vuln_id or '(unknown vuln)'}"
                            + (f"; fix in {','.join(fix_versions)}" if fix_versions else "")
                        ),
                        path=f"<dependency:{pkg}>",
                        extra={
                            "package": pkg,
                            "installed_version": version,
                            "vuln_id": vuln_id,
                            "fix_versions": fix_versions,
                            "description": vuln.get("description"),
                            "aliases": vuln.get("aliases", []),
                        },
                    )
                )

        # Record what scope + ignore-list actually ran, so the result is
        # self-describing for downstream verification.
        scope_meta: dict[str, Any] = {
            "python_exe": str(python_exe) if python_exe else "<ambient>",
            "ignored_vulns": list(ignore_vulns),
        }

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
            extra=scope_meta,
        )

    @staticmethod
    def _dump_freeze(python_exe: Path) -> Path | None:
        """Run ``<python_exe> -m pip freeze`` and write to a temp file. Returns
        the path or None on any failure (the pillar surfaces a loud error)."""
        import tempfile
        try:
            result = subprocess.run(
                [str(python_exe), "-m", "pip", "freeze", "--all"],
                capture_output=True, text=True, timeout=60,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None
        if result.returncode != 0 or not result.stdout.strip():
            return None
        # Write the freeze output to a temp file for pip-audit --requirement.
        # Filter out editable installs (-e ...) since pip-audit chokes on them
        # and they're typically the project itself (not interesting for vuln scan).
        lines = [
            line for line in result.stdout.splitlines()
            if line.strip() and not line.strip().startswith("-e ")
            and "==" in line  # only standard pinned-version lines
        ]
        if not lines:
            return None
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix="_pip_freeze_for_audit.txt", delete=False
        )
        tmp.write("\n".join(lines) + "\n")
        tmp.close()
        return Path(tmp.name)
