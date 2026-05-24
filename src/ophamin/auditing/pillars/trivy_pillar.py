"""TrivyConfigPillar — wraps Aqua's ``trivy config`` (IaC misconfiguration scan).

Fills a real gap: no other pillar inspects *infrastructure* definitions.
``trivy config`` runs Trivy's built-in policy checks over Dockerfiles,
docker-compose files, Kubernetes manifests, Terraform, Helm, etc., flagging
misconfigurations (root user, missing HEALTHCHECK, privileged containers,
secrets in env, etc.).

Runs from the official image ``aquasec/trivy`` via Docker. JSON output
(``--format json``) groups misconfigurations by target file. One finding per
misconfiguration.

Severity follows Trivy's native scale (CRITICAL / HIGH / MEDIUM / LOW /
UNKNOWN). License: Apache-2.0. Needs network on first run (fetches the
checks bundle).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from ophamin.auditing.base import Finding, FindingSeverity, PillarResult
from ophamin.auditing.pillars._docker_pillar import DockerAuditPillar


_SEVERITY_MAP: dict[str, FindingSeverity] = {
    "CRITICAL": FindingSeverity.CRITICAL,
    "HIGH": FindingSeverity.HIGH,
    "MEDIUM": FindingSeverity.MEDIUM,
    "LOW": FindingSeverity.LOW,
    "UNKNOWN": FindingSeverity.INFO,
}


class TrivyConfigPillar(DockerAuditPillar):
    """``trivy config --format json /src`` (Dockerized) as an audit pillar."""

    name = "trivy_config"
    image = "aquasec/trivy:latest"
    allow_network = True  # fetches the policy/checks bundle on first run

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

        t0 = time.perf_counter()
        try:
            result = self.run_docker(
                target,
                ["config", "--quiet", "--format", "json", self.mount_point],
                timeout_s,
            )
        except Exception as exc:  # noqa: BLE001 — surfaced as a loud error result
            return self.error_result(
                target, f"trivy docker run failed: {type(exc).__name__}: {exc}",
                wall_time_s=time.perf_counter() - t0,
            )
        wall = time.perf_counter() - t0

        if result.returncode != 0:
            return self.error_result(
                target,
                f"trivy exit_code={result.returncode}: "
                f"{(result.stderr or '').strip()[:200]}",
                exit_code=result.returncode, wall_time_s=wall,
            )

        try:
            data = json.loads(result.stdout or "{}")
        except json.JSONDecodeError as exc:
            return self.error_result(
                target, f"trivy produced non-JSON output: {exc}",
                exit_code=result.returncode, wall_time_s=wall,
            )

        findings: list[Finding] = []
        for res in data.get("Results", []) or []:
            tgt = res.get("Target", "")
            host = self.host_path(f"/src/{tgt}" if not tgt.startswith("/src") else tgt, target)
            for mc in res.get("Misconfigurations", []) or []:
                sev = (mc.get("Severity", "UNKNOWN") or "UNKNOWN").upper()
                cause = mc.get("CauseMetadata", {}) or {}
                findings.append(
                    Finding(
                        pillar_name=self.name,
                        rule_id=mc.get("ID") or mc.get("AVDID") or "trivy/misconfig",
                        severity=_SEVERITY_MAP.get(sev, FindingSeverity.MEDIUM),
                        message=(mc.get("Title") or mc.get("Description") or "")[:300],
                        path=host,
                        line=int(cause.get("StartLine", 0) or 0),
                        extra={
                            "avd_id": mc.get("AVDID"),
                            "type": mc.get("Type"),
                            "resolution": mc.get("Resolution"),
                            "url": mc.get("PrimaryURL"),
                            "trivy_severity": sev,
                        },
                    )
                )

        return PillarResult(
            pillar_name=self.name,
            tool_name="trivy",
            tool_version=self.tool_version(),
            status="ok",
            target_path=target,
            findings=tuple(findings),
            raw_stdout_bytes=len(result.stdout or ""),
            raw_stderr_bytes=len(result.stderr or ""),
            exit_code=result.returncode,
            wall_time_s=wall,
            extra={"image": self.image, "scan": "config/misconfiguration"},
        )
