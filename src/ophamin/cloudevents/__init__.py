"""CloudEvents 1.0 wrapper for Ophamin signed proofs.

This subpackage wraps :class:`EmpiricalProofRecord` artefacts in
[CloudEvents 1.0](https://github.com/cloudevents/spec) structured-mode
envelopes so event-stream consumers (Kafka, EventBridge, Knative,
NATS, anything CloudEvents-aware) can route Ophamin records
natively.

Two functions:

- :func:`wrap` — wrap a proof (as a parsed dict OR a JSON string)
  in a CloudEvents 1.0 structured-mode envelope. Returns a
  ``dict[str, Any]`` ready for `json.dumps` + emit.
- :func:`unwrap` — extract the proof from an envelope. Returns the
  proof's dict; verifying the proof's signature is the caller's
  responsibility (use ``ophamin.interfaces._impls.verify_proof_impl``
  or call ``EmpiricalProofRecord.verify_signature`` after parsing).

Attributes used:

| Attribute | Value |
|---|---|
| ``specversion`` | ``"1.0"`` |
| ``id`` | the proof's content-addressed ``proof_id`` (SHA-256 hex) |
| ``source`` | caller-supplied, e.g. ``urn:my-deployment:ophamin`` |
| ``type`` | default ``"dev.ophamin.proof.emitted.v1"`` (caller-overridable) |
| ``time`` | the record's ``identity.created_at`` (ISO-8601) |
| ``datacontenttype`` | ``"application/json"`` |
| ``dataschema`` | ``"https://github.com/IdirBenSlama/Ophamin/blob/main/SCHEMAS.md#empiricalproofrecord--1-0"`` |
| ``ophaminschemaversion`` | the record's ``schema_version`` (CloudEvents extension attribute) |
| ``ophaminversion`` | the framework version that emitted the record |
| ``ophaminverdict`` | ``VALIDATED`` / ``REFUTED`` / ``INCONCLUSIVE`` |
| ``data`` | the full proof record (structured mode) |

CloudEvents extension attributes (``ophamin*``) follow the
[CloudEvents naming convention](https://github.com/cloudevents/spec/blob/main/cloudevents/spec.md#attribute-naming-convention):
lowercase letters + digits, no separators, ≤ 20 characters.
"""

from __future__ import annotations

from ophamin.cloudevents.envelope import (
    CLOUDEVENTS_SPEC_VERSION,
    DEFAULT_TYPE,
    OPHAMIN_DATASCHEMA,
    CloudEventEnvelopeError,
    unwrap,
    validate_envelope,
    wrap,
)

__all__ = [
    "CLOUDEVENTS_SPEC_VERSION",
    "DEFAULT_TYPE",
    "OPHAMIN_DATASCHEMA",
    "CloudEventEnvelopeError",
    "unwrap",
    "validate_envelope",
    "wrap",
]
