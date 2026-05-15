"""Cross-cutting interop layer — exports Ophamin's signed records into the
standard formats that traditional engineering tools consume.

The wheels (seeing, measuring, comparing, auditing, instrumenting, reporting,
inspecting) all produce signed records in Ophamin's own JSON schema. The
interop layer translates those records into formats other tools already
understand, so Ophamin output flows into existing toolchains without anyone
having to learn Ophamin's schema.

Phase 1 exports (built):

  SARIF 2.1.0      AuditRecord  → VS Code Problems pane, GitHub code-scanning,
                                   GitLab CI security panel, Azure DevOps,
                                   any SARIF-aware tool
  JUnit XML        EmpiricalProofRecord → GitHub Actions / GitLab CI /
                                          CircleCI / Jenkins / TeamCity /
                                          Bitrise / any CI's test-result
                                          aggregator

Both formats are well-specified industry standards (SARIF 2.1.0 OASIS spec;
JUnit XML the de-facto Jenkins schema). The exports preserve provenance —
the original record's hash + signature land in the SARIF tool's
``invocations`` block / JUnit's ``properties`` block so downstream consumers
can trace back to the signed Ophamin artefact.

Phase 2 exports (deferred):

  OpenTelemetry    instrumenting profiles → Jaeger / Tempo / Honeycomb
  Prometheus       cross-run drift / scenario rates → Grafana dashboards
  CycloneDX SBOM   dependency lists → security tooling
  MLflow runs      proof records → MLflow tracking server

CLI:

  ophamin export <record.json> --format sarif|junit-xml [--output <path>]
"""

from __future__ import annotations

from ophamin.interop.junit_xml import (
    JUnitXMLExporter,
    proof_record_to_junit_xml,
)
from ophamin.interop.mlflow_export import (
    MLflowExporter,
    export_audit_record,
    export_proof_record,
)
from ophamin.interop.sarif import (
    SARIFExporter,
    audit_record_to_sarif,
)

__all__ = [
    "JUnitXMLExporter",
    "MLflowExporter",
    "SARIFExporter",
    "audit_record_to_sarif",
    "export_audit_record",
    "export_proof_record",
    "proof_record_to_junit_xml",
]
