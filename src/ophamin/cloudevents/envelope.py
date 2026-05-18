"""CloudEvents 1.0 envelope construction + extraction.

Reference: https://github.com/cloudevents/spec/blob/main/cloudevents/spec.md
Schema: https://github.com/cloudevents/spec/blob/main/cloudevents/formats/json-format.md

Three public functions:

- :func:`wrap` — wrap a proof in a CloudEvents 1.0 envelope.
- :func:`unwrap` — extract the proof from an envelope.
- :func:`validate_envelope` — assert an envelope satisfies the
  CloudEvents 1.0 structured-mode required-attributes set.

No external dependencies. The CloudEvents 1.0 structured-mode JSON
shape is small enough to encode directly without pulling in the
``cloudevents`` Python package.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from ophamin import __version__
from ophamin.measuring.proof.record import _canonical

#: CloudEvents specification version this module targets.
CLOUDEVENTS_SPEC_VERSION: str = "1.0"

#: Default CloudEvents ``type`` attribute when the caller does not
#: override. Follows the reverse-DNS convention CloudEvents recommends.
DEFAULT_TYPE: str = "dev.ophamin.proof.emitted.v1"

#: ``dataschema`` URI pointing at the normative SCHEMAS.md section
#: that defines the embedded record's wire shape.
OPHAMIN_DATASCHEMA: str = (
    "https://github.com/IdirBenSlama/Ophamin/blob/main/SCHEMAS.md"
    "#empiricalproofrecord--10"
)

#: Required CloudEvents 1.0 top-level attributes (per the spec's
#: REQUIRED list — see §3.1).
_REQUIRED_ATTRIBUTES: frozenset[str] = frozenset({
    "specversion",
    "id",
    "source",
    "type",
})

#: Lowercase-alphanumeric attribute-name regex per CloudEvents §3.1.
#: Extension attributes (everything except the spec's listed names)
#: MUST match this regex.
_EXTENSION_ATTRIBUTE_NAME_RE = re.compile(r"^[a-z0-9]{1,20}$")


class CloudEventEnvelopeError(ValueError):
    """Raised when wrap / unwrap / validation finds a malformed event."""


def _resolve_proof_dict(proof: dict[str, Any] | str | bytes) -> dict[str, Any]:
    """Accept the proof as a parsed dict OR a JSON string/bytes.

    Returns the parsed dict.
    """
    if isinstance(proof, dict):
        return proof
    if isinstance(proof, (bytes, bytearray)):
        proof_text: str = bytes(proof).decode("utf-8")
    elif isinstance(proof, str):
        proof_text = proof
    else:
        raise CloudEventEnvelopeError(
            f"proof must be a dict, str, or bytes (got {type(proof).__name__})"
        )
    try:
        parsed: Any = json.loads(proof_text)
    except json.JSONDecodeError as exc:
        raise CloudEventEnvelopeError(
            f"proof JSON text could not be parsed: {exc}"
        ) from exc
    if not isinstance(parsed, dict):
        raise CloudEventEnvelopeError(
            "proof JSON text must decode to a JSON object (got "
            f"{type(parsed).__name__})"
        )
    return parsed


def _compute_proof_id(proof: dict[str, Any]) -> str:
    """Return the proof's content-addressed proof_id (SHA-256 of the
    canonical body bytes — everything except signature + proof_id).

    Mirrors :meth:`EmpiricalProofRecord.proof_id` so a wrapped event's
    ``id`` is stable across encoders.
    """
    body = {k: v for k, v in proof.items() if k not in ("signature", "proof_id")}
    canonical = _canonical(body)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def wrap(
    proof: dict[str, Any] | str | bytes,
    *,
    source: str,
    event_type: str = DEFAULT_TYPE,
    extra_extensions: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Wrap an Ophamin signed proof in a CloudEvents 1.0 envelope.

    Args:
        proof: the proof record. Accepted as a parsed dict, a JSON
            string, or JSON bytes.
        source: the CloudEvents ``source`` attribute — a URI-reference
            identifying the producer. CloudEvents recommends a
            ``urn:`` or ``https://`` scheme; e.g.
            ``urn:my-deployment:ophamin:scenarios:spearman-crosscheck``.
        event_type: the CloudEvents ``type`` attribute. Defaults to
            :data:`DEFAULT_TYPE`. Override when emitting different
            event flavours (e.g. ``dev.ophamin.proof.refuted.v1``).
        extra_extensions: optional caller-supplied extension
            attributes. Names MUST match CloudEvents §3.1's
            ``[a-z0-9]{1,20}`` regex; values MUST be strings.

    Returns:
        A dict ready for ``json.dumps`` + emit on Kafka / HTTP /
        any CloudEvents-aware sink. The envelope is in
        CloudEvents 1.0 **structured mode** — the proof itself sits
        in the ``data`` attribute.

    Raises:
        CloudEventEnvelopeError: on malformed proof, missing
            ``source``, or extension-name violations.
    """
    proof_dict = _resolve_proof_dict(proof)
    if not source:
        raise CloudEventEnvelopeError(
            "source is required (CloudEvents §3.1 — a URI-reference "
            "identifying the producer)"
        )
    if not event_type:
        raise CloudEventEnvelopeError(
            "event_type is required (CloudEvents §3.1)"
        )

    envelope: dict[str, Any] = {
        "specversion": CLOUDEVENTS_SPEC_VERSION,
        "id": proof_dict.get("proof_id") or _compute_proof_id(proof_dict),
        "source": source,
        "type": event_type,
        "datacontenttype": "application/json",
        "dataschema": OPHAMIN_DATASCHEMA,
    }
    # CloudEvents ``time`` — pull from the record's identity block
    # when present; this is ISO-8601 already per Ophamin's emitter.
    identity = proof_dict.get("identity") or {}
    if isinstance(identity, dict):
        created_at = identity.get("created_at")
        if isinstance(created_at, str) and created_at:
            envelope["time"] = created_at
        ophamin_version_emitted = identity.get("ophamin_version", "")
    else:
        ophamin_version_emitted = ""

    # Ophamin-specific extension attributes — names lowercased,
    # ≤ 20 chars per §3.1. Values stringified for spec compliance.
    envelope["ophaminversion"] = (
        str(ophamin_version_emitted) if ophamin_version_emitted else __version__
    )
    envelope["ophaminschema"] = str(proof_dict.get("schema_version", ""))
    verdict = proof_dict.get("verdict") or {}
    if isinstance(verdict, dict):
        envelope["ophaminverdict"] = str(verdict.get("outcome", ""))
    else:
        envelope["ophaminverdict"] = ""

    # Reserved attribute names — CloudEvents 1.0 spec-defined + the
    # ``data`` payload + Ophamin's own ``ophamin*`` extension surface.
    # Caller-supplied extensions cannot shadow any of these.
    reserved: frozenset[str] = frozenset(envelope.keys()) | frozenset({"data"})

    if extra_extensions:
        for k, v in extra_extensions.items():
            if not _EXTENSION_ATTRIBUTE_NAME_RE.match(k):
                raise CloudEventEnvelopeError(
                    f"extension attribute name {k!r} violates CloudEvents "
                    f"§3.1 — must match [a-z0-9]{{1,20}}"
                )
            if not isinstance(v, str):
                raise CloudEventEnvelopeError(
                    f"extension attribute {k!r} value must be a string "
                    f"(got {type(v).__name__})"
                )
            if k in reserved:
                raise CloudEventEnvelopeError(
                    f"extension attribute {k!r} collides with a "
                    f"built-in CloudEvents attribute"
                )
            envelope[k] = v

    envelope["data"] = proof_dict
    return envelope


def unwrap(envelope: dict[str, Any] | str | bytes) -> dict[str, Any]:
    """Extract the embedded proof from a CloudEvents envelope.

    Args:
        envelope: parsed dict OR JSON string / bytes.

    Returns:
        The proof dict that the producer wrapped.

    Raises:
        CloudEventEnvelopeError: if the envelope is malformed or the
        ``data`` attribute is missing / wrong-typed.
    """
    if isinstance(envelope, (bytes, bytearray)):
        envelope_text = bytes(envelope).decode("utf-8")
    elif isinstance(envelope, str):
        envelope_text = envelope
    elif isinstance(envelope, dict):
        envelope_dict = envelope
        envelope_text = ""
    else:
        raise CloudEventEnvelopeError(
            f"envelope must be a dict, str, or bytes (got {type(envelope).__name__})"
        )
    if envelope_text:
        try:
            parsed: Any = json.loads(envelope_text)
        except json.JSONDecodeError as exc:
            raise CloudEventEnvelopeError(
                f"envelope JSON could not be parsed: {exc}"
            ) from exc
        if not isinstance(parsed, dict):
            raise CloudEventEnvelopeError(
                "envelope JSON must decode to a JSON object"
            )
        envelope_dict = parsed

    validate_envelope(envelope_dict)

    data = envelope_dict.get("data")
    if not isinstance(data, dict):
        raise CloudEventEnvelopeError(
            "envelope's 'data' attribute must be a JSON object "
            f"(got {type(data).__name__}); structured mode is "
            f"required for Ophamin proofs"
        )
    return data


def validate_envelope(envelope: dict[str, Any]) -> None:
    """Assert the envelope has every required CloudEvents 1.0 attribute.

    Implements the REQUIRED-attribute subset of CloudEvents §3.1.
    Does NOT validate the embedded proof's signature — that's the
    consumer's responsibility (use
    ``ophamin.interfaces._impls.verify_proof_impl``).

    Raises:
        CloudEventEnvelopeError: on any missing / malformed required
            attribute.
    """
    if not isinstance(envelope, dict):
        raise CloudEventEnvelopeError(
            f"envelope must be a JSON object (got {type(envelope).__name__})"
        )
    for required in _REQUIRED_ATTRIBUTES:
        if required not in envelope:
            raise CloudEventEnvelopeError(
                f"envelope missing required CloudEvents attribute: {required}"
            )
        if not isinstance(envelope[required], str):
            raise CloudEventEnvelopeError(
                f"envelope's {required} attribute must be a string "
                f"(got {type(envelope[required]).__name__})"
            )
        if not envelope[required]:
            raise CloudEventEnvelopeError(
                f"envelope's {required} attribute is empty"
            )
    sv = envelope["specversion"]
    if sv != CLOUDEVENTS_SPEC_VERSION:
        raise CloudEventEnvelopeError(
            f"envelope specversion is {sv!r}; this wrapper targets "
            f"{CLOUDEVENTS_SPEC_VERSION!r}"
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
