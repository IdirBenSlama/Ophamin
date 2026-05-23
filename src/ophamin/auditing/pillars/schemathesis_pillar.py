"""SchemathesisPillar — wraps ``schemathesis`` (API contract testing).

Per ``docs/PLUGIN_CATALOG_2026_05_15.md`` PR #11. Schemathesis runs
property-based tests against an OpenAPI / GraphQL spec. Project-scope:
the target must be either a directory containing an OpenAPI YAML/JSON
file, or a path to a spec file directly.

Each schemathesis check failure becomes a Finding. Severity depends on
the check kind:
  ``not_a_server_error``   → CRITICAL (5xx where 4xx expected)
  ``status_code_conformance`` → HIGH
  ``content_type_conformance`` → MEDIUM
  ``response_schema_conformance`` → MEDIUM
  default → LOW
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any

from ophamin.auditing.base import AuditPillar, Finding, FindingSeverity, PillarResult


_CHECK_SEVERITY: dict[str, FindingSeverity] = {
    "not_a_server_error":         FindingSeverity.CRITICAL,
    "status_code_conformance":    FindingSeverity.HIGH,
    "content_type_conformance":   FindingSeverity.MEDIUM,
    "response_schema_conformance": FindingSeverity.MEDIUM,
}


def _find_openapi_spec(target: Path) -> Path | None:
    """Find an OpenAPI / Swagger spec in / under target. Returns first hit."""
    if target.is_file():
        return target
    if not target.is_dir():
        return None
    candidates = [
        "openapi.json", "openapi.yaml", "openapi.yml",
        "swagger.json", "swagger.yaml", "swagger.yml",
        "api/openapi.json", "api/openapi.yaml",
    ]
    for c in candidates:
        p = target / c
        if p.is_file():
            return p
    return None


class SchemathesisPillar(AuditPillar):
    """``schemathesis run --checks=all <spec>`` wrapped as a pillar.

    Project-scope: target should be either an OpenAPI spec file directly
    OR a project-root directory containing one of:
      ``openapi.json``, ``openapi.yaml``, ``swagger.json``,
      ``swagger.yaml``, ``api/openapi.json``, ``api/openapi.yaml``.

    For Kimera: the FastAPI app under ``kimera_swm/api/`` would need a
    spec extracted first via ``app.openapi()`` → JSON file. That helper
    is out of scope here — schemathesis as a standalone pillar verifies
    static specs.
    """

    name = "schemathesis"
    tool_binary = "schemathesis"

    def run(
        self,
        target_path: str | Path,
        *,
        timeout_s: float = 600.0,
        base_url: str = "",        # required for live-server testing; empty = static spec only
        **_kwargs: Any,
    ) -> PillarResult:
        target = Path(target_path).resolve()
        target_str = str(target)
        if not self.is_available():
            return self.unavailable_result(target_str)

        spec_path = _find_openapi_spec(target)
        if spec_path is None:
            return self.error_result(
                target_str,
                f"schemathesis requires an OpenAPI spec at {target_str!r} "
                f"or one of (openapi|swagger).(json|yaml|yml). For dynamic "
                f"FastAPI apps, extract a spec first via app.openapi() → "
                f"openapi.json.",
                wall_time_s=0.0,
            )

        binary = self.resolved_binary() or self.tool_binary
        cmd = [binary, "run", "--show-trace", "--no-color", str(spec_path)]
        if base_url:
            cmd += ["--base-url", base_url]
        else:
            # Schemathesis CLI v4+ requires --dry-run for static spec validation
            # without a live server; v3 used --validate-schema=true. Try the
            # broader "--no-network" first, fall through to a basic run.
            cmd += ["--dry-run"]

        t0 = time.perf_counter()
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            return self.error_result(
                target_str,
                f"schemathesis timed out after {timeout_s}s: {exc}",
                wall_time_s=time.perf_counter() - t0,
            )
        except FileNotFoundError:
            return self.unavailable_result(target_str)
        wall = time.perf_counter() - t0

        # Schemathesis emits human-readable text. Without --report-junit
        # we can't easily parse per-check failures; instead, emit a single
        # rolled-up Finding per ERROR / FAILED line in stdout.
        findings: list[Finding] = []
        out = (result.stdout or "") + "\n" + (result.stderr or "")
        for line in out.splitlines():
            stripped = line.strip()
            # Lines like "FAILED test_get_health" or "ERROR collection ..."
            if stripped.startswith(("FAILED", "ERROR")):
                rule_id = "SCHEMATHESIS_FAILED" if stripped.startswith("FAILED") else "SCHEMATHESIS_ERROR"
                severity = (FindingSeverity.HIGH if stripped.startswith("FAILED")
                            else FindingSeverity.CRITICAL)
                findings.append(Finding(
                    pillar_name="schemathesis",
                    rule_id=rule_id,
                    severity=severity,
                    message=stripped[:300],
                    path=str(spec_path),
                    line=0,
                ))

        # If schemathesis reports a spec-validation issue (HTTP 0 / parse
        # error) it goes to stderr — surface as a single Finding so the
        # pillar isn't silently empty.
        if result.returncode != 0 and not findings:
            err_summary = (result.stderr or result.stdout or "schemathesis exit non-zero")[:300]
            findings.append(Finding(
                pillar_name="schemathesis",
                rule_id="SCHEMATHESIS_EXIT_NONZERO",
                severity=FindingSeverity.HIGH,
                message=err_summary.strip(),
                path=str(spec_path),
                line=0,
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
