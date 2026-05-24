"""DetectSecretsPillar — wraps Yelp's ``detect-secrets`` (credential scanner).

Fills a real gap in the audit wheel: none of the other pillars look for
*secrets* (API keys, passwords, tokens, high-entropy strings) committed into
source. ``detect-secrets scan`` runs an ensemble of plugins (keyword,
base64/hex high-entropy, AWS/Azure/GitHub/JWT/private-key detectors, …) and
emits a JSON "baseline" listing every candidate by file + line.

Output shape (``detect-secrets scan <path>``)::

    {"results": {"<file>": [{"type": "...", "line_number": N,
                             "hashed_secret": "...", "is_verified": false}]},
     "version": "1.5.0", ...}

Severity: a committed secret is credential-leak territory, so every candidate
maps to HIGH. The raw secret value is never captured — detect-secrets reports
only a salted hash, which is exactly what we keep in ``extra``.

License: Apache-2.0 (permissive). Install: ``pip install detect-secrets``.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from ophamin.auditing.base import AuditPillar, Finding, FindingSeverity, PillarResult


class DetectSecretsPillar(AuditPillar):
    """``detect-secrets scan <target>`` wrapped as an audit pillar."""

    name = "detect_secrets"
    tool_binary = "detect-secrets"

    def run(
        self,
        target_path: str | Path,
        *,
        timeout_s: float = 600.0,
        **_kwargs: Any,
    ) -> PillarResult:
        target = str(Path(target_path).resolve())
        if not self.is_available():
            return self.unavailable_result(target)

        binary = self.resolved_binary() or self.tool_binary
        # --all-files: scan every file recursively, not just git-tracked ones.
        # A secrets audit must see untracked files too (a local .env with live
        # credentials is exactly the threat a tracked-only scan would miss).
        # detect-secrets walks relative to the working directory, so we run it
        # *inside* the target (cwd=target) and scan ".", then absolutise paths.
        cmd = [binary, "scan", "--all-files", "."]
        t0 = time.perf_counter()
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout_s, cwd=target,
            )
        except subprocess.TimeoutExpired as exc:
            return self.error_result(
                target, f"detect-secrets timed out after {timeout_s}s: {exc}",
                wall_time_s=time.perf_counter() - t0,
            )
        except FileNotFoundError:
            return self.unavailable_result(target)
        wall = time.perf_counter() - t0

        if result.returncode != 0:
            return self.error_result(
                target,
                f"detect-secrets exit_code={result.returncode}: "
                f"{(result.stderr or '').strip()[:200]}",
                exit_code=result.returncode, wall_time_s=wall,
            )

        try:
            data = json.loads(result.stdout or "{}")
        except json.JSONDecodeError as exc:
            return self.error_result(
                target, f"detect-secrets produced non-JSON output: {exc}",
                exit_code=result.returncode, wall_time_s=wall,
            )

        findings: list[Finding] = []
        results = data.get("results", {})
        if isinstance(results, dict):
            for file_path, secrets in results.items():
                for s in secrets or []:
                    if not isinstance(s, dict):
                        continue
                    stype = s.get("type", "secret")
                    # detect-secrets paths are relative to the scanned root
                    # (cwd=target); absolutise so reports/SARIF carry full paths.
                    abs_path = str((Path(target) / str(file_path)).resolve())
                    findings.append(
                        Finding(
                            pillar_name=self.name,
                            rule_id=stype,
                            severity=FindingSeverity.HIGH,
                            message=f"Potential secret ({stype}) detected",
                            path=abs_path,
                            line=int(s.get("line_number", 0) or 0),
                            extra={
                                "secret_type": stype,
                                "hashed_secret": s.get("hashed_secret"),
                                "is_verified": s.get("is_verified", False),
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
            extra={"plugins": [p.get("name") for p in data.get("plugins_used", [])]},
        )
