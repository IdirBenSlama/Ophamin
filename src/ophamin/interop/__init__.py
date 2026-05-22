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
  CycloneDX SBOM   dependency lists → security tooling
  MLflow runs      proof records → MLflow tracking server
  in-toto / DSSE   signed proofs → Sigstore / SLSA / Rekor / cosign /
                                    policy-controller / slsa-verifier — the
                                    entire supply-chain attestation ecosystem
  RO-Crate 1.2     signed proofs → self-describing research-artifact
                                    packaging; FAIR data principles;
                                    research-data infrastructure (Galaxy,
                                    Zenodo, WorkflowHub)
  OpenLineage 2.0  signed proofs → data-pipeline lineage events
                                    (Airflow, dbt, Spark, Flink, Marquez,
                                    Astronomer; CNCF-incubating spec)

All formats are well-specified industry standards (SARIF 2.1.0 OASIS spec;
JUnit XML the de-facto Jenkins schema; in-toto Attestation Framework v1
[ITE-6]; DSSE secure-systems-lab spec). Exports preserve provenance — the
original record's hash + signature land in the SARIF tool's ``invocations``
block, JUnit's ``properties`` block, or in-toto's ``predicate.signature``
field, so downstream consumers can trace back to the signed Ophamin artefact.

Phase 2 exports (deferred):

  OpenTelemetry    instrumenting profiles → Jaeger / Tempo / Honeycomb
  Prometheus       cross-run drift / scenario rates → Grafana dashboards

CLI:

  ophamin export <record.json> --format sarif|junit-xml [--output <path>]
"""

from __future__ import annotations

from ophamin.interop.cyclonedx import (
    CycloneDXExporter,
    build_cyclonedx_sbom_from_env,
    build_cyclonedx_sbom_from_record,
)
from ophamin.interop.in_toto import (
    DSSE_INTOTO_PAYLOAD_TYPE,
    IN_TOTO_STATEMENT_V1_TYPE,
    OPHAMIN_PREDICATE_TYPE_V1,
    to_dsse_envelope,
    to_in_toto_statement,
    verify_dsse_envelope,
)
from ophamin.interop.junit_xml import (
    JUnitXMLExporter,
    proof_record_to_junit_xml,
)
from ophamin.interop.mlflow_export import (
    MLflowExporter,
    export_audit_record,
    export_proof_record,
)
from ophamin.interop.openlineage import (
    DEFAULT_NAMESPACE,
    OPENLINEAGE_PRODUCER_URL_BASE,
    OPENLINEAGE_SCHEMA_URL,
    OPHAMIN_RUNID_NAMESPACE,
    new_run_id,
    to_openlineage_complete_event,
    to_openlineage_event,
    to_openlineage_fail_event,
    to_openlineage_running_event,
    to_openlineage_start_event,
)
from ophamin.interop.ro_crate import (
    DEFAULT_PROOF_FILENAME,
    RO_CRATE_CONFORMS_TO_V1_2,
    RO_CRATE_CONTEXT_V1_2,
    RO_CRATE_METADATA_FILENAME,
    to_ro_crate_metadata,
    write_ro_crate,
)
from ophamin.interop.sarif import (
    SARIFExporter,
    audit_record_to_sarif,
)
from ophamin.interop.tool_acquisition import (
    ACQUIRE_GATE_ENV,
    ToolCandidate,
    acquisition_plan,
    evaluate_candidate,
    register_acquired_tool,
    verify_acquired_tool,
)
from ophamin.interop.toolkit_registry import (
    Toolkit,
    ToolkitConfigError,
    toolkit_registry,
)

__all__ = [
    "CycloneDXExporter",
    "ACQUIRE_GATE_ENV",
    "ToolCandidate",
    "acquisition_plan",
    "evaluate_candidate",
    "register_acquired_tool",
    "verify_acquired_tool",
    "Toolkit",
    "ToolkitConfigError",
    "toolkit_registry",
    "DEFAULT_NAMESPACE",
    "DEFAULT_PROOF_FILENAME",
    "DSSE_INTOTO_PAYLOAD_TYPE",
    "IN_TOTO_STATEMENT_V1_TYPE",
    "JUnitXMLExporter",
    "MLflowExporter",
    "OPENLINEAGE_PRODUCER_URL_BASE",
    "OPENLINEAGE_SCHEMA_URL",
    "OPHAMIN_PREDICATE_TYPE_V1",
    "OPHAMIN_RUNID_NAMESPACE",
    "RO_CRATE_CONFORMS_TO_V1_2",
    "RO_CRATE_CONTEXT_V1_2",
    "RO_CRATE_METADATA_FILENAME",
    "SARIFExporter",
    "audit_record_to_sarif",
    "build_cyclonedx_sbom_from_env",
    "build_cyclonedx_sbom_from_record",
    "export_audit_record",
    "export_proof_record",
    "new_run_id",
    "proof_record_to_junit_xml",
    "to_dsse_envelope",
    "to_in_toto_statement",
    "to_openlineage_complete_event",
    "to_openlineage_event",
    "to_openlineage_fail_event",
    "to_openlineage_running_event",
    "to_openlineage_start_event",
    "to_ro_crate_metadata",
    "verify_dsse_envelope",
    "write_ro_crate",
]
