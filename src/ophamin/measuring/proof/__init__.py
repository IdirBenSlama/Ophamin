"""The Ophamin Empirical Proof Record — the official result artifact.

    record.py     the nine-section EmpiricalProofRecord, content-addressed + signed
    schema.json   the official JSON Schema for proof.json

A proof is bulletproof when it is falsifiable, pre-registered, traceable,
reproducible, attributed and tamper-evident. ``EmpiricalProofRecord.validate``
enforces every one of those properties.
"""

from pathlib import Path

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
]
