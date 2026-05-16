"""CycloneDX SBOM exporter — current Python environment → CycloneDX 1.5.

CycloneDX is the OWASP-maintained Software Bill of Materials standard.
Output produced here is compatible with:

  - GitHub's dependency graph
  - GitLab dependency scanning
  - OWASP Dependency-Track
  - Snyk / Anchore / Trivy / any SBOM-aware supply-chain tool

Two construction paths:

  build_cyclonedx_sbom_from_env()        sample the current venv via
                                          ``importlib.metadata.distributions``
                                          and emit one ``component`` per
                                          installed package
  build_cyclonedx_sbom_from_record()      reconstruct the SBOM from a signed
                                          proof record's
                                          ``reproduction.environment`` dict
                                          (pip-freeze-like ``name==version``
                                          strings)

Both produce the same CycloneDX 1.5 JSON shape; the latter is useful when
auditing the dependency set that produced a specific proof record on a
different machine.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from importlib import metadata as _metadata
from pathlib import Path
from typing import Any

from ophamin import __version__ as OPHAMIN_VERSION


CYCLONEDX_SPEC_VERSION = "1.5"


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pypi_purl(name: str, version: str) -> str:
    """Build a Package URL (purl) for a PyPI package.

    Format: ``pkg:pypi/<name>@<version>`` — the canonical CycloneDX
    component identifier for Python packages.
    """
    # The purl spec mandates lowercase package names for pypi
    safe_name = name.strip().lower().replace("_", "-")
    return f"pkg:pypi/{safe_name}@{version}"


def _component_from_distribution(dist: _metadata.Distribution) -> dict[str, Any]:
    """Build one CycloneDX component entry from an installed Distribution."""
    name = (dist.metadata.get("Name") or "").strip()
    version = (dist.metadata.get("Version") or "").strip()
    component: dict[str, Any] = {
        "type": "library",
        "bom-ref": _pypi_purl(name, version),
        "name": name,
        "version": version,
        "purl": _pypi_purl(name, version),
    }
    # optional fields from PKG-INFO when present
    if (description := (dist.metadata.get("Summary") or "").strip()):
        component["description"] = description
    if (homepage := (dist.metadata.get("Home-page") or "").strip()):
        component["externalReferences"] = [{"type": "website", "url": homepage}]
    if (license_text := (dist.metadata.get("License") or "").strip()):
        component["licenses"] = [{"license": {"name": license_text[:120]}}]
    return component


def build_cyclonedx_sbom_from_env(
    *,
    application_name: str = "ophamin",
    application_version: str | None = None,
    serial_number: str | None = None,
) -> dict[str, Any]:
    """Build a CycloneDX 1.5 SBOM from the current Python environment.

    ``application_name`` + ``application_version`` describe the thing the
    SBOM is *for*; default to Ophamin itself.
    """
    components: list[dict[str, Any]] = []
    for dist in _metadata.distributions():
        try:
            component = _component_from_distribution(dist)
        except Exception:  # noqa: BLE001 — tolerate malformed metadata
            continue
        if not component["name"]:
            continue
        components.append(component)
    # deterministic ordering for a content-addressable SBOM
    components.sort(key=lambda c: (c["name"].lower(), c["version"]))

    app_version = application_version or OPHAMIN_VERSION
    return {
        "bomFormat": "CycloneDX",
        "specVersion": CYCLONEDX_SPEC_VERSION,
        "serialNumber": serial_number or f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": _now_utc_iso(),
            "tools": [{
                "vendor": "ophamin",
                "name": "ophamin",
                "version": OPHAMIN_VERSION,
            }],
            "component": {
                "type": "application",
                "bom-ref": _pypi_purl(application_name, app_version),
                "name": application_name,
                "version": app_version,
                "purl": _pypi_purl(application_name, app_version),
            },
            "properties": [
                {"name": "python.version", "value": sys.version.split()[0]},
                {"name": "python.implementation",
                 "value": sys.implementation.name},
                {"name": "platform.os", "value": os.name},
                {"name": "platform.sys", "value": sys.platform},
            ],
        },
        "components": components,
    }


def build_cyclonedx_sbom_from_record(
    record: dict[str, Any],
    *,
    serial_number: str | None = None,
) -> dict[str, Any]:
    """Build a SBOM from a signed proof record's reproduction.environment dict.

    The proof record's environment is ``dict[str, str]`` (package name →
    version, captured at the time of the run). We synthesise CycloneDX
    components from those entries; the SBOM is descriptive (lacks the rich
    PKG-INFO metadata) but pins the dependency set as evidence.
    """
    if not isinstance(record, dict):
        raise TypeError("build_cyclonedx_sbom_from_record expects a dict")
    reproduction = record.get("reproduction") or {}
    env = reproduction.get("environment") or {}
    if not isinstance(env, dict) or not env:
        raise ValueError(
            "record's reproduction.environment is missing or empty; "
            "cannot build a SBOM from it"
        )

    components: list[dict[str, Any]] = []
    for name, version in env.items():
        name_str = str(name).strip()
        version_str = str(version).strip()
        if not name_str:
            continue
        components.append({
            "type": "library",
            "bom-ref": _pypi_purl(name_str, version_str),
            "name": name_str,
            "version": version_str,
            "purl": _pypi_purl(name_str, version_str),
        })
    components.sort(key=lambda c: (c["name"].lower(), c["version"]))

    proof_id = str(record.get("proof_id") or record.get("audit_id") or "")
    return {
        "bomFormat": "CycloneDX",
        "specVersion": CYCLONEDX_SPEC_VERSION,
        "serialNumber": serial_number or f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": _now_utc_iso(),
            "tools": [{
                "vendor": "ophamin",
                "name": "ophamin",
                "version": OPHAMIN_VERSION,
            }],
            "component": {
                "type": "application",
                "bom-ref": f"ophamin-record-{proof_id[:12]}",
                "name": "ophamin-signed-record",
                "version": proof_id[:12] or "unknown",
            },
            "properties": [
                {"name": "ophamin.record_id", "value": proof_id},
                {"name": "ophamin.signature",
                 "value": str(record.get("signature", ""))[:120]},
                {"name": "ophamin.schema_version",
                 "value": str(record.get("schema_version", ""))},
            ],
        },
        "components": components,
    }


class CycloneDXExporter:
    """Convenience wrapper for the CycloneDX SBOM exporters."""

    def export_env(
        self,
        out_path: str | Path,
        *,
        application_name: str = "ophamin",
        application_version: str | None = None,
    ) -> Path:
        sbom = build_cyclonedx_sbom_from_env(
            application_name=application_name,
            application_version=application_version,
        )
        return self._write(sbom, out_path)

    def export_record(self, record: dict[str, Any], out_path: str | Path) -> Path:
        sbom = build_cyclonedx_sbom_from_record(record)
        return self._write(sbom, out_path)

    @staticmethod
    def _write(sbom: dict[str, Any], out_path: str | Path) -> Path:
        out = Path(out_path)
        if out.suffix.lower() not in (".json", ".cdx.json"):
            out = out.with_suffix(".cdx.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(sbom, indent=2, default=str), encoding="utf-8")
        return out
