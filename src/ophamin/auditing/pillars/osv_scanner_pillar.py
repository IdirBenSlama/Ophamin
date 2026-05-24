"""OsvScannerPillar — wraps Google's ``osv-scanner`` (OSV.dev SCA).

Complements ``pip_audit_pillar``: where pip-audit resolves the *installed*
Python environment against PyPI advisories, osv-scanner walks a project's
**lockfiles / manifests** (requirements.txt, poetry.lock, package-lock.json,
go.mod, Cargo.lock, …) and matches them against the cross-ecosystem
`OSV.dev <https://osv.dev>`_ database. Two different lenses on dependency risk;
running both is genuine defence-in-depth.

Runs from the official image ``ghcr.io/google/osv-scanner`` via Docker. JSON
output (``--format json``) groups vulnerabilities by source → package. One
finding per (package, vulnerability).

Severity: taken from each vuln's ``database_specific.severity`` when present,
else bucketed from the group's max CVSS score, else HIGH (an exploitable
dependency is must-fix territory).

License: Apache-2.0. Needs network (queries the OSV.dev API).
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
    "MODERATE": FindingSeverity.MEDIUM,
    "MEDIUM": FindingSeverity.MEDIUM,
    "LOW": FindingSeverity.LOW,
}


def _fixed_versions(vuln: dict[str, Any], pkg_name: str) -> list[str]:
    """Extract the patched versions from an OSV vuln's affected[].ranges[].events.

    Each range carries ``introduced``/``fixed`` events; the ``fixed`` value is
    the first version that resolves the advisory — exactly what a dependency
    bump should target. Scoped to the affected entry matching ``pkg_name``.
    """
    out: list[str] = []
    for aff in vuln.get("affected", []) or []:
        if (aff.get("package", {}) or {}).get("name", "") != pkg_name:
            continue
        for rng in aff.get("ranges", []) or []:
            for ev in rng.get("events", []) or []:
                fx = ev.get("fixed")
                if fx and fx not in out:
                    out.append(fx)
    return out


def _cvss_to_severity(score: str) -> FindingSeverity:
    """Bucket a numeric CVSS base score (0-10) into a FindingSeverity."""
    try:
        v = float(score)
    except (TypeError, ValueError):
        return FindingSeverity.HIGH
    if v >= 9.0:
        return FindingSeverity.CRITICAL
    if v >= 7.0:
        return FindingSeverity.HIGH
    if v >= 4.0:
        return FindingSeverity.MEDIUM
    return FindingSeverity.LOW


_SEVERITY_RANK: dict[FindingSeverity, int] = {
    FindingSeverity.CRITICAL: 4,
    FindingSeverity.HIGH: 3,
    FindingSeverity.MEDIUM: 2,
    FindingSeverity.LOW: 1,
    FindingSeverity.INFO: 0,
}


def _worst_severity(*candidates: FindingSeverity | None) -> FindingSeverity:
    """Return the HIGHEST-rank (worst) non-None severity — a security scanner
    must never downgrade a vuln, so a coarse db label can only RAISE, never lower,
    the CVSS-derived rating. Defaults to HIGH when no signal is available (an
    exploitable dependency with unknown severity is must-fix territory)."""
    present = [c for c in candidates if c is not None]
    if not present:
        return FindingSeverity.HIGH
    return max(present, key=lambda s: _SEVERITY_RANK[s])


class OsvScannerPillar(DockerAuditPillar):
    """``osv-scanner --format json -r /src`` (Dockerized) as an audit pillar."""

    name = "osv_scanner"
    image = "ghcr.io/google/osv-scanner:latest"
    allow_network = True  # queries the OSV.dev advisory API

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
                target, ["--format", "json", "-r", self.mount_point], timeout_s,
            )
        except Exception as exc:  # noqa: BLE001 — surfaced as a loud error result
            return self.error_result(
                target, f"osv-scanner docker run failed: {type(exc).__name__}: {exc}",
                wall_time_s=time.perf_counter() - t0,
            )
        wall = time.perf_counter() - t0

        # osv-scanner: 0 = no vulns, 1 = vulns found, other = error.
        if result.returncode not in (0, 1):
            return self.error_result(
                target,
                f"osv-scanner exit_code={result.returncode}: "
                f"{(result.stderr or '').strip()[:200]}",
                exit_code=result.returncode, wall_time_s=wall,
            )

        try:
            data = json.loads(result.stdout or "{}")
        except json.JSONDecodeError as exc:
            return self.error_result(
                target, f"osv-scanner produced non-JSON output: {exc}",
                exit_code=result.returncode, wall_time_s=wall,
            )

        findings: list[Finding] = []
        for res in data.get("results", []) or []:
            src_path = (res.get("source", {}) or {}).get("path", "")
            host = self.host_path(src_path, target)
            for pkg_entry in res.get("packages", []) or []:
                pkg = pkg_entry.get("package", {}) or {}
                name = pkg.get("name", "")
                version = pkg.get("version", "")
                # Per-vuln CVSS base score: map each vuln id/alias to ITS group's
                # max_severity (osv groups bundle related ids with a numeric CVSS
                # base). The old code kept only the LAST group's score and applied
                # it to every vuln (B2); this keys it correctly per vuln.
                cvss_by_id: dict[str, str] = {}
                for g in pkg_entry.get("groups", []) or []:
                    ms = g.get("max_severity", "") or ""
                    for gid in g.get("ids", []) or []:
                        cvss_by_id[gid] = ms
                for vuln in pkg_entry.get("vulnerabilities", []) or []:
                    vid = vuln.get("id", "")
                    aliases = vuln.get("aliases", []) or []
                    db_sev = ((vuln.get("database_specific", {}) or {})
                              .get("severity", "") or "").upper()
                    # CVSS base score for THIS vuln (by id, then any alias).
                    cvss = cvss_by_id.get(vid, "")
                    if not cvss:
                        for a in aliases:
                            if a in cvss_by_id:
                                cvss = cvss_by_id[a]
                                break
                    # Worst of CVSS-derived and the coarse db label — NEVER let a
                    # stale db_specific 'LOW' mask a real 9.1 CVSS (B1).
                    severity = _worst_severity(
                        _cvss_to_severity(cvss) if cvss else None,
                        _SEVERITY_MAP.get(db_sev),
                    )
                    fix_versions = _fixed_versions(vuln, name)
                    findings.append(
                        Finding(
                            pillar_name=self.name,
                            rule_id=vid or f"osv/{name}",
                            severity=severity,
                            message=(
                                f"{name} {version} affected by {vid}"
                                + (f" ({', '.join(aliases)})" if aliases else "")
                                + (f"; fixed in {', '.join(fix_versions)}" if fix_versions else "")
                                + (f": {vuln.get('summary')}" if vuln.get("summary") else "")
                            ),
                            path=host,
                            extra={
                                "package": name,
                                "installed_version": version,
                                "ecosystem": pkg.get("ecosystem"),
                                "vuln_id": vid,
                                "aliases": aliases,
                                "fix_versions": fix_versions,
                                "max_cvss": cvss,
                                "db_severity": db_sev,
                            },
                        )
                    )

        return PillarResult(
            pillar_name=self.name,
            tool_name="osv-scanner",
            tool_version=self.tool_version(),
            status="ok",
            target_path=target,
            findings=tuple(findings),
            raw_stdout_bytes=len(result.stdout or ""),
            raw_stderr_bytes=len(result.stderr or ""),
            exit_code=result.returncode,
            wall_time_s=wall,
            extra={"image": self.image, "scanner": "osv.dev"},
        )
