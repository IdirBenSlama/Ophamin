"""The Ophamin Empirical Proof Record — the official result artifact.

    record.py     the nine-section EmpiricalProofRecord, content-addressed + signed
    schema.json   the official JSON Schema for proof.json
    codec.py      single-call load / validate / verify / ingest interface

A proof is bulletproof when it is falsifiable, pre-registered, traceable,
reproducible, attributed and tamper-evident. ``EmpiricalProofRecord.validate``
enforces every one of those properties.

The :mod:`ophamin.measuring.proof.codec` module is the canonical surface
for reading proof records back into memory — load, schema-validate,
record-validate, and signature-verify with one call (:func:`codec.ingest`).
Walk a proof corpus with :func:`codec.list_proofs`.
"""

from pathlib import Path

from ophamin.measuring.proof.codec import (
    ProofCodecError,
    ProofDecodeError,
    ProofIndex,
    ProofListEntry,
    ProofSchemaError,
    ProofSchemaVersionMismatchError,
    ProofSignatureError,
    ProofValidationError,
    ValidationReport,
    build_index,
    dump,
    ingest,
    iter_proofs,
    list_proofs,
    load,
    validate,
    validate_schema,
    verify_signature,
)
from ophamin.measuring.proof.record import (
    INCONCLUSIVE,
    REFUTED,
    SCHEMA_VERSION,
    VALIDATED,
    Claim,
    DatasetRef,
    EmpiricalProofRecord,
    PillarEvidence,
    PreRegistration,
    Reproduction,
    Threshold,
    Verdict,
    build_environment_lock,
    content_hash,
)

#: absolute path to the official JSON Schema for proof.json
SCHEMA_PATH = Path(__file__).with_name("schema.json")

__all__ = [
    "EmpiricalProofRecord",
    "Claim",
    "Threshold",
    "PreRegistration",
    "DatasetRef",
    "PillarEvidence",
    "Verdict",
    "Reproduction",
    "VALIDATED",
    "REFUTED",
    "INCONCLUSIVE",
    "SCHEMA_VERSION",
    "SCHEMA_PATH",
    "build_environment_lock",
    "content_hash",
    # codec surface
    "ProofCodecError",
    "ProofDecodeError",
    "ProofIndex",
    "ProofListEntry",
    "ProofSchemaError",
    "ProofSchemaVersionMismatchError",
    "ProofSignatureError",
    "ProofValidationError",
    "ValidationReport",
    "build_index",
    "dump",
    "ingest",
    "iter_proofs",
    "list_proofs",
    "load",
    "validate",
    "validate_schema",
    "verify_signature",
]
