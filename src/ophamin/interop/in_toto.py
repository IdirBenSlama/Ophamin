"""in-toto Attestation Framework (ITE-6) exporter for signed Ophamin proofs.

The in-toto Attestation Framework defines a common envelope format
(``Statement``) that Sigstore, SLSA, and other supply-chain tools
consume directly. Wrapping Ophamin's :class:`EmpiricalProofRecord`
as an in-toto Statement lets the framework's signed empirical
claims flow through every existing in-toto-aware toolchain:
``cosign`` for signing, ``policy-controller`` for admission control,
``rekor`` for transparency logging, ``slsa-verifier`` for chain-of-
custody verification.

Per the in-toto Attestation Framework v1 (ITE-6):

.. code-block:: json

    {
      "_type": "https://in-toto.io/Statement/v1",
      "predicateType": "<URI naming the claim shape>",
      "subject": [
        {"name": "<identifier>", "digest": {"sha256": "<hex>"}}
      ],
      "predicate": {<arbitrary JSON — the claim itself>}
    }

For Ophamin's case:

- ``predicateType`` = a stable URI identifying the
  ``EmpiricalProofRecord`` shape (versioned with the SCHEMA_VERSION
  so a downstream verifier knows what predicate fields to expect).
- ``subject`` = the proof_id treated as the artifact digest.
  ``proof_id`` is content-addressed (SHA-256 over sections 1-8 in
  canonical form), so it doubles as a perfectly-shaped in-toto
  subject digest.
- ``predicate`` = the full proof JSON body (sections 1-8). Section
  9 (the HMAC signature) is preserved alongside but not folded
  into the predicate — the in-toto envelope is signed separately
  via DSSE if the consumer chooses.

Two construction paths:

  :func:`to_in_toto_statement`     EmpiricalProofRecord → Statement dict
  :func:`to_dsse_envelope`         EmpiricalProofRecord + key → DSSE
                                   envelope (signed Statement) ready
                                   for upload to Rekor or storage in
                                   a transparency log

DSSE (Dead Simple Signing Envelope) is the standard transport for
in-toto Statements; it carries the Statement JSON as a
base64-encoded payload alongside one or more signatures over the
canonical PAE form (Pre-Authentication Encoding) defined in
`DSSE spec <https://github.com/secure-systems-lab/dsse>`_.

For documentation context see:

- https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md
- https://github.com/secure-systems-lab/dsse
- https://slsa.dev/blog/2023/05/in-toto-and-slsa
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any

from ophamin import __version__ as OPHAMIN_VERSION
from ophamin.measuring.proof.record import EmpiricalProofRecord

# --------------------------------------------------------------------------
# Constants — pinned by tests as @Stable surfaces. Changing any of these
# values is a major-version bump (consumers reading the predicate URI
# would need a migration).
# --------------------------------------------------------------------------

#: URI for the in-toto Statement v1 type.
IN_TOTO_STATEMENT_V1_TYPE = "https://in-toto.io/Statement/v1"

#: URI identifying the predicate shape this module emits. Versioned
#: alongside Ophamin's :data:`SCHEMA_VERSION` so a downstream verifier
#: reading the predicateType knows whether their consumer expects v1
#: shape (sections 1-8 as documented in SCHEMAS.md) or a future version.
#: The URI is anchored at the GitHub repo per in-toto's "use a URL that
#: stays stable" convention.
OPHAMIN_PREDICATE_TYPE_V1 = (
    "https://github.com/IdirBenSlama/Ophamin/blob/main/SCHEMAS.md"
    "#empirical-proof-record-v1"
)

#: DSSE payloadType for in-toto Statement v1 envelopes.
DSSE_INTOTO_PAYLOAD_TYPE = "application/vnd.in-toto+json"


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def to_in_toto_statement(
    proof: EmpiricalProofRecord,
    *,
    subject_name: str | None = None,
) -> dict[str, Any]:
    """Wrap a signed Ophamin proof as an in-toto Statement v1.

    The returned dict conforms to in-toto's Statement v1 spec
    (`spec/v1/statement.md
    <https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md>`_).
    The proof's ``proof_id`` (content-addressed SHA-256 over sections
    1-8) is used as the subject's ``digest.sha256``; the full proof
    JSON is embedded as the ``predicate``.

    Parameters
    ----------
    proof
        A signed :class:`EmpiricalProofRecord`. The proof MUST be
        signed (``proof.signature`` non-empty); a Statement over an
        unsigned proof would mislead downstream verifiers about the
        claim's authenticity.
    subject_name
        Optional human-readable identifier for the subject. Defaults
        to ``"empirical-proof-record-<short-id>"`` derived from the
        first 16 chars of ``proof_id``. The in-toto spec allows any
        string here; consumers display it for context.

    Returns
    -------
    dict
        A Statement v1 dict ready to be serialized to JSON. The
        caller is responsible for the JSON encoding step (use
        ``json.dumps(stmt, sort_keys=True, separators=(",", ":"))``
        for canonical bytes).

    Raises
    ------
    ValueError
        If the proof has no signature, or if ``proof.proof_id`` is
        empty/malformed.
    """
    if not proof.signature:
        raise ValueError(
            "to_in_toto_statement: proof must be signed before wrapping; "
            "call .sign(key) first"
        )
    proof_id = proof.proof_id
    if not proof_id:
        raise ValueError(
            "to_in_toto_statement: proof.proof_id is empty — record may be "
            "malformed"
        )
    if len(proof_id) != 64 or not all(c in "0123456789abcdef" for c in proof_id):
        raise ValueError(
            f"to_in_toto_statement: proof.proof_id is not a 64-char "
            f"lowercase hex SHA-256 digest (got {proof_id!r})"
        )

    name = subject_name or f"empirical-proof-record-{proof_id[:16]}"

    return {
        "_type": IN_TOTO_STATEMENT_V1_TYPE,
        "predicateType": OPHAMIN_PREDICATE_TYPE_V1,
        "subject": [
            {
                "name": name,
                "digest": {"sha256": proof_id},
            }
        ],
        # The full proof body (sections 1-8) lives in predicate.body,
        # alongside the HMAC signature (section 9) in predicate.signature.
        # Downstream verifiers can re-canonicalize predicate.body and
        # check against predicate.signature using the same Ophamin
        # verification path Python uses.
        "predicate": {
            "ophamin_version": OPHAMIN_VERSION,
            "schema_version": proof.schema_version,
            "body": proof._body(),
            "signature": proof.signature,
        },
    }


def to_dsse_envelope(
    proof: EmpiricalProofRecord,
    key: bytes,
    *,
    keyid: str = "",
    subject_name: str | None = None,
) -> dict[str, Any]:
    """Wrap a signed Ophamin proof as a DSSE-signed in-toto envelope.

    DSSE (Dead Simple Signing Envelope) is the canonical transport
    for in-toto Statements. The envelope shape:

    .. code-block:: json

        {
          "payloadType": "application/vnd.in-toto+json",
          "payload": "<base64 of Statement JSON>",
          "signatures": [
            {"keyid": "<optional>", "sig": "<base64 HMAC-SHA256>"}
          ]
        }

    The signature is computed over DSSE's Pre-Authentication Encoding
    (PAE):

    .. code-block:: text

        DSSEv1 <len(payloadType)> <payloadType> <len(payload)> <payload>

    Per `the DSSE spec <https://github.com/secure-systems-lab/dsse>`_
    — the PAE prevents signature-substitution attacks across
    payloadTypes.

    Parameters
    ----------
    proof
        Signed :class:`EmpiricalProofRecord` (same constraint as
        :func:`to_in_toto_statement`).
    key
        HMAC-SHA256 key for signing the DSSE envelope. Typically the
        same key that signed the inner proof; passing the same key
        produces a self-consistent double-signature (both the inner
        proof HMAC and the outer DSSE HMAC verify under the same
        key).
    keyid
        Optional opaque identifier for the key. Stored verbatim in
        the signature's ``keyid`` field — consumers use this to
        select the right verification key when multiple keys are
        registered. Defaults to empty (single-key deployments).
    subject_name
        Forwarded to :func:`to_in_toto_statement`.

    Returns
    -------
    dict
        A DSSE envelope dict ready to be serialized. The envelope
        is the canonical transport format for Rekor (Sigstore's
        transparency log) and for offline storage in an attestation
        archive.

    Raises
    ------
    ValueError
        If the proof is unsigned or the key is empty.
    """
    if not key:
        raise ValueError("to_dsse_envelope: key must be non-empty bytes")

    statement = to_in_toto_statement(proof, subject_name=subject_name)
    payload_bytes = _canonical_json_bytes(statement)
    payload_b64 = base64.b64encode(payload_bytes).decode("ascii")

    pae = _build_pae(DSSE_INTOTO_PAYLOAD_TYPE, payload_bytes)
    sig_bytes = hmac.new(key, pae, hashlib.sha256).digest()
    sig_b64 = base64.b64encode(sig_bytes).decode("ascii")

    return {
        "payloadType": DSSE_INTOTO_PAYLOAD_TYPE,
        "payload": payload_b64,
        "signatures": [
            {
                "keyid": keyid,
                "sig": sig_b64,
            }
        ],
    }


def verify_dsse_envelope(
    envelope: dict[str, Any],
    key: bytes,
) -> bool:
    """Verify the DSSE envelope's HMAC signature under the given key.

    Recomputes the Pre-Authentication Encoding from the envelope's
    ``payloadType`` and base64-decoded ``payload`` and HMAC-compares
    against each signature in the envelope. Returns ``True`` if any
    signature verifies (DSSE allows multiple signatures over the
    same payload).

    This does NOT verify the inner Ophamin proof's HMAC signature —
    that lives inside ``predicate.signature`` and uses Ophamin's
    canonical-form encoding (per SCHEMAS.md R1-R11), not DSSE PAE.
    Callers wanting end-to-end verification should:

    1. ``verify_dsse_envelope(envelope, dsse_key)``
    2. Decode the inner Statement, extract ``predicate.body`` +
       ``predicate.signature``, and run Ophamin's standard verify
       path against ``predicate.body`` with the Ophamin sign key.

    Parameters
    ----------
    envelope
        A DSSE envelope dict (output of :func:`to_dsse_envelope`).
    key
        HMAC-SHA256 key.

    Returns
    -------
    bool
        ``True`` iff at least one signature in the envelope verifies.
    """
    payload_type = envelope.get("payloadType", "")
    payload_b64 = envelope.get("payload", "")
    signatures = envelope.get("signatures", [])
    if not (payload_type and payload_b64 and signatures):
        return False

    try:
        payload_bytes = base64.b64decode(payload_b64)
    except (ValueError, TypeError):
        return False

    pae = _build_pae(payload_type, payload_bytes)
    expected = hmac.new(key, pae, hashlib.sha256).digest()

    for sig in signatures:
        sig_b64 = sig.get("sig", "")
        if not sig_b64:
            continue
        try:
            sig_bytes = base64.b64decode(sig_b64)
        except (ValueError, TypeError):
            continue
        if hmac.compare_digest(expected, sig_bytes):
            return True
    return False


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _canonical_json_bytes(obj: Any) -> bytes:
    """Canonical JSON bytes for hashing / signing.

    Uses ``sort_keys=True`` + tight separators + ``ensure_ascii=True``.
    This matches Ophamin's own canonical-form rules (SCHEMAS.md R1-R11)
    so a downstream verifier reading the DSSE payload sees the same
    byte sequence regardless of language / platform.
    """
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def _build_pae(payload_type: str, payload: bytes) -> bytes:
    """Build DSSE Pre-Authentication Encoding (PAE) for HMAC input.

    Per `DSSE spec <https://github.com/secure-systems-lab/dsse>`_:

    .. code-block:: text

        PAE(type, body) = "DSSEv1" SP LEN(type) SP type SP LEN(body) SP body

    where SP is a single space (0x20). The construction prevents an
    attacker from substituting a signature from one payloadType
    onto a different payloadType.
    """
    pt = payload_type.encode("utf-8")
    return b"DSSEv1 " + str(len(pt)).encode("ascii") + b" " + pt + b" " + str(len(payload)).encode("ascii") + b" " + payload
