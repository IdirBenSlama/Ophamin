"""Hardening pins for the in-toto Attestation Framework (ITE-6) exporter.

Each test pins a load-bearing property of the export contract — Statement v1
shape, DSSE envelope structure, PAE encoding, signature round-trip — so a
future edit that drifts the canonical form fails loudly before it can break
a downstream Sigstore / SLSA / Rekor consumer.

The tests construct real ``EmpiricalProofRecord`` instances (via the same
helper pattern as ``test_proof.py``) and sign them with HMAC-SHA256 — the
in-toto wrapper accepts *any* signed Ophamin proof, so testing through the
real object catches drift at both the proof boundary and the in-toto layer.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json

import pytest

from ophamin.interop.in_toto import (
    DSSE_INTOTO_PAYLOAD_TYPE,
    IN_TOTO_STATEMENT_V1_TYPE,
    OPHAMIN_PREDICATE_TYPE_V1,
    _build_pae,
    _canonical_json_bytes,
    to_dsse_envelope,
    to_in_toto_statement,
    verify_dsse_envelope,
)
from ophamin.measuring.proof import (
    Claim,
    DatasetRef,
    EmpiricalProofRecord,
    PillarEvidence,
    PreRegistration,
    Reproduction,
    Threshold,
    Verdict,
)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _signed_proof(key: bytes = b"ophamin-test-key") -> EmpiricalProofRecord:
    """Build a complete, valid, signed EmpiricalProofRecord for in-toto wrapping.

    Mirrors ``test_proof._complete_record`` so the in-toto layer is exercised
    against the canonical shape the rest of the codebase produces.
    """
    threshold = Threshold(
        metric="dissonance_slope", comparator=">=", value=0.1, units="per cycle"
    )
    claim = Claim(
        statement="Substrate doubt rises as internal documents contradict public filings.",
        operationalization="I.cma pooled slope of the zetetic dissonance gradient",
        threshold=threshold,
        h0="dissonance slope <= 0.1 per cycle",
        h1="dissonance slope > 0.1 per cycle",
    )
    prereg = PreRegistration(
        config_hash="cfg" + "0" * 61,
        data_hash="dat" + "0" * 61,
        analysis_plan="cumulative meta-analysis over chronological batches",
        sweep_grid={"batch_size": [1000, 5000]},
    )
    datasets = [
        DatasetRef(
            name="test-corpus",
            content_hash="abc" + "0" * 61,
            n_records=100,
            source="https://example.invalid/",
            kind="email_corpus",
        )
    ]
    evidence = [
        PillarEvidence(
            pillar="I.cma",
            statistic_name="pooled_slope",
            statistic_value=0.18,
            library="statsmodels",
            library_version="0.14.6",
            effect_size=0.18,
            ci_low=0.14,
            ci_high=0.22,
            p_value=1e-9,
            cross_check="passed",
        )
    ]
    record = EmpiricalProofRecord(
        claim=claim,
        preregistration=prereg,
        datasets=datasets,
        substrate_name="kimera-swm",
        substrate_git_commit="9596c681092358be",
        evidence=evidence,
        verdict=Verdict.decide(0.18, threshold),
        reproduction=Reproduction(command="ophamin scenario test"),
        provenance={"entity": {}, "activity": {}, "agent": {}},
        ophamin_version="0.34.0-test",
        ophamin_git_commit="deadbeefcafe",
    )
    record.sign(key)
    return record


# --------------------------------------------------------------------------
# Constants — pinned as @Stable URIs. Drifting them is a major-version
# bump for downstream verifiers and MUST be intentional.
# --------------------------------------------------------------------------


def test_statement_type_is_in_toto_v1():
    """The Statement._type constant matches the in-toto v1 spec URI exactly."""
    assert IN_TOTO_STATEMENT_V1_TYPE == "https://in-toto.io/Statement/v1"


def test_predicate_type_is_versioned_and_stable():
    """The predicateType URI is anchored at the Ophamin SCHEMAS.md anchor."""
    assert OPHAMIN_PREDICATE_TYPE_V1.startswith("https://github.com/IdirBenSlama/Ophamin/")
    assert "SCHEMAS.md" in OPHAMIN_PREDICATE_TYPE_V1
    assert "empirical-proof-record-v1" in OPHAMIN_PREDICATE_TYPE_V1


def test_dsse_payload_type_matches_in_toto_spec():
    """DSSE envelopes carrying in-toto Statements use the canonical media type."""
    assert DSSE_INTOTO_PAYLOAD_TYPE == "application/vnd.in-toto+json"


# --------------------------------------------------------------------------
# to_in_toto_statement — Statement v1 shape
# --------------------------------------------------------------------------


def test_statement_has_four_top_level_keys():
    """A Statement is exactly {_type, predicateType, subject, predicate}."""
    stmt = to_in_toto_statement(_signed_proof())
    assert set(stmt.keys()) == {"_type", "predicateType", "subject", "predicate"}


def test_statement_type_field_points_to_in_toto_v1():
    stmt = to_in_toto_statement(_signed_proof())
    assert stmt["_type"] == IN_TOTO_STATEMENT_V1_TYPE


def test_statement_predicate_type_is_ophamin_v1():
    stmt = to_in_toto_statement(_signed_proof())
    assert stmt["predicateType"] == OPHAMIN_PREDICATE_TYPE_V1


def test_subject_is_list_with_one_entry():
    """in-toto allows multi-subject Statements; Ophamin emits exactly one."""
    stmt = to_in_toto_statement(_signed_proof())
    assert isinstance(stmt["subject"], list)
    assert len(stmt["subject"]) == 1


def test_subject_digest_matches_proof_id():
    """The subject's sha256 digest IS the proof_id (content-addressed)."""
    proof = _signed_proof()
    stmt = to_in_toto_statement(proof)
    digest = stmt["subject"][0]["digest"]
    assert digest == {"sha256": proof.proof_id}


def test_subject_digest_is_64_hex_chars():
    """SHA-256 digest format invariant (in-toto consumers parse hex)."""
    stmt = to_in_toto_statement(_signed_proof())
    sha256 = stmt["subject"][0]["digest"]["sha256"]
    assert len(sha256) == 64
    assert all(c in "0123456789abcdef" for c in sha256)


def test_default_subject_name_derived_from_proof_id():
    proof = _signed_proof()
    stmt = to_in_toto_statement(proof)
    assert stmt["subject"][0]["name"] == f"empirical-proof-record-{proof.proof_id[:16]}"


def test_custom_subject_name_passed_through():
    stmt = to_in_toto_statement(
        _signed_proof(), subject_name="my-named-attestation"
    )
    assert stmt["subject"][0]["name"] == "my-named-attestation"


# --------------------------------------------------------------------------
# Predicate — embeds the full proof body + signature
# --------------------------------------------------------------------------


def test_predicate_has_ophamin_version_and_schema_version():
    proof = _signed_proof()
    stmt = to_in_toto_statement(proof)
    assert stmt["predicate"]["ophamin_version"]  # non-empty
    assert stmt["predicate"]["schema_version"] == proof.schema_version


def test_predicate_body_matches_proof_body():
    """The predicate.body IS the signable body — downstream verifiers
    re-canonicalize this and HMAC-check against predicate.signature."""
    proof = _signed_proof()
    stmt = to_in_toto_statement(proof)
    assert stmt["predicate"]["body"] == proof._body()


def test_predicate_signature_matches_proof_signature():
    proof = _signed_proof()
    stmt = to_in_toto_statement(proof)
    assert stmt["predicate"]["signature"] == proof.signature


def test_predicate_body_is_dict():
    """Body must be a plain dict (JSON-serializable) — not a Pydantic model
    or arbitrary object that would break json.dumps."""
    stmt = to_in_toto_statement(_signed_proof())
    assert isinstance(stmt["predicate"]["body"], dict)


def test_statement_is_json_serializable_canonical():
    """The whole Statement round-trips through json.dumps with the canonical
    settings Ophamin uses everywhere — no exotic types leak in."""
    stmt = to_in_toto_statement(_signed_proof())
    encoded = json.dumps(stmt, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    # round-trip is byte-identical (idempotent canonical form)
    decoded = json.loads(encoded)
    re_encoded = json.dumps(decoded, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    assert encoded == re_encoded


# --------------------------------------------------------------------------
# Unsigned / malformed proof rejection
# --------------------------------------------------------------------------


def test_unsigned_proof_is_rejected():
    """An unsigned proof MUST NOT be wrappable — that would mislead
    downstream consumers about authenticity."""
    proof = _signed_proof()
    proof.signature = ""  # forcibly strip the signature
    with pytest.raises(ValueError, match="proof must be signed"):
        to_in_toto_statement(proof)


def test_empty_proof_id_is_rejected():
    """If proof_id is somehow empty/malformed the wrapper refuses LOUD."""

    # Force a malformed proof_id by monkey-patching the proof_id property
    class _BrokenProof:
        signature = "deadbeef"
        proof_id = ""  # not a property, just an attribute for the duck-type

    with pytest.raises(ValueError, match="proof_id is empty"):
        to_in_toto_statement(_BrokenProof())  # type: ignore[arg-type]


def test_non_hex_proof_id_is_rejected():
    """proof_id must be 64-char lowercase hex sha256 — anything else
    breaks downstream subject-digest verification."""

    class _BadProof:
        signature = "deadbeef"
        proof_id = "ZZZZ" * 16  # 64 chars but not hex

    with pytest.raises(ValueError, match="64-char lowercase hex"):
        to_in_toto_statement(_BadProof())  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# DSSE envelope structure
# --------------------------------------------------------------------------


def test_dsse_envelope_has_three_top_level_keys():
    env = to_dsse_envelope(_signed_proof(), b"dsse-key")
    assert set(env.keys()) == {"payloadType", "payload", "signatures"}


def test_dsse_envelope_payload_type_matches_constant():
    env = to_dsse_envelope(_signed_proof(), b"dsse-key")
    assert env["payloadType"] == DSSE_INTOTO_PAYLOAD_TYPE


def test_dsse_envelope_payload_is_base64_of_canonical_statement():
    proof = _signed_proof()
    env = to_dsse_envelope(proof, b"dsse-key")
    decoded = base64.b64decode(env["payload"])
    expected = _canonical_json_bytes(to_in_toto_statement(proof))
    assert decoded == expected


def test_dsse_envelope_has_exactly_one_signature_by_default():
    """The single-signer path emits one signature; multi-signer needs
    a deliberate extension (not currently supported)."""
    env = to_dsse_envelope(_signed_proof(), b"dsse-key")
    assert isinstance(env["signatures"], list)
    assert len(env["signatures"]) == 1


def test_dsse_signature_has_keyid_and_sig_fields():
    env = to_dsse_envelope(_signed_proof(), b"dsse-key")
    sig = env["signatures"][0]
    assert set(sig.keys()) == {"keyid", "sig"}


def test_dsse_keyid_preserved():
    env = to_dsse_envelope(_signed_proof(), b"dsse-key", keyid="rsa-2026-05")
    assert env["signatures"][0]["keyid"] == "rsa-2026-05"


def test_dsse_default_keyid_is_empty_string():
    """Single-key deployments leave keyid empty (matches DSSE spec example)."""
    env = to_dsse_envelope(_signed_proof(), b"dsse-key")
    assert env["signatures"][0]["keyid"] == ""


def test_dsse_signature_is_valid_base64():
    env = to_dsse_envelope(_signed_proof(), b"dsse-key")
    # Should not raise
    sig_bytes = base64.b64decode(env["signatures"][0]["sig"])
    # HMAC-SHA256 always produces 32 bytes
    assert len(sig_bytes) == 32


def test_dsse_empty_key_is_rejected():
    """Empty signing key is a programmer error — refuse loudly."""
    with pytest.raises(ValueError, match="key must be non-empty"):
        to_dsse_envelope(_signed_proof(), b"")


# --------------------------------------------------------------------------
# DSSE round-trip: sign → verify
# --------------------------------------------------------------------------


def test_dsse_round_trip_verifies():
    """Signing with key K and verifying with key K returns True."""
    key = b"dsse-round-trip-key"
    env = to_dsse_envelope(_signed_proof(), key)
    assert verify_dsse_envelope(env, key) is True


def test_dsse_verify_with_wrong_key_returns_false():
    """Wrong key → False (NOT a raised exception; verify is a query)."""
    env = to_dsse_envelope(_signed_proof(), b"correct-key")
    assert verify_dsse_envelope(env, b"wrong-key") is False


def test_dsse_verify_with_tampered_payload_returns_false():
    """Payload bytes mutated after signing → verify fails."""
    key = b"dsse-tamper-key"
    env = to_dsse_envelope(_signed_proof(), key)
    # Re-encode a tampered version of the payload
    tampered_stmt = json.loads(base64.b64decode(env["payload"]))
    tampered_stmt["predicate"]["body"]["tampered"] = True
    env["payload"] = base64.b64encode(
        _canonical_json_bytes(tampered_stmt)
    ).decode("ascii")
    assert verify_dsse_envelope(env, key) is False


def test_dsse_verify_with_tampered_signature_returns_false():
    """Signature bytes mutated after signing → verify fails."""
    key = b"dsse-tamper-sig-key"
    env = to_dsse_envelope(_signed_proof(), key)
    # Flip a byte in the signature
    sig_bytes = bytearray(base64.b64decode(env["signatures"][0]["sig"]))
    sig_bytes[0] ^= 0xFF
    env["signatures"][0]["sig"] = base64.b64encode(bytes(sig_bytes)).decode("ascii")
    assert verify_dsse_envelope(env, key) is False


def test_dsse_verify_on_empty_envelope_returns_false():
    """Missing payloadType / payload / signatures → False, not crash."""
    assert verify_dsse_envelope({}, b"any-key") is False


def test_dsse_verify_on_invalid_base64_payload_returns_false():
    env = {
        "payloadType": DSSE_INTOTO_PAYLOAD_TYPE,
        "payload": "!!!not-valid-base64!!!",
        "signatures": [{"keyid": "", "sig": base64.b64encode(b"x" * 32).decode("ascii")}],
    }
    assert verify_dsse_envelope(env, b"any-key") is False


def test_dsse_verify_returns_true_if_any_signature_matches():
    """DSSE allows multiple signatures — at least one valid is sufficient."""
    key = b"valid-key"
    env = to_dsse_envelope(_signed_proof(), key)
    # Inject a second, invalid signature alongside the valid one
    env["signatures"].insert(
        0, {"keyid": "junk", "sig": base64.b64encode(b"x" * 32).decode("ascii")}
    )
    assert verify_dsse_envelope(env, key) is True


# --------------------------------------------------------------------------
# PAE (Pre-Authentication Encoding) — DSSE spec correctness
# --------------------------------------------------------------------------


def test_pae_format_matches_dsse_spec():
    """PAE = "DSSEv1 " + len(type) + " " + type + " " + len(payload) + " " + payload."""
    pae = _build_pae("application/vnd.in-toto+json", b"hello")
    # Manually construct expected per spec
    expected = (
        b"DSSEv1 "
        + str(len("application/vnd.in-toto+json")).encode("ascii")
        + b" "
        + b"application/vnd.in-toto+json"
        + b" "
        + str(len(b"hello")).encode("ascii")
        + b" "
        + b"hello"
    )
    assert pae == expected


def test_pae_prefix_is_dssev1():
    """The DSSEv1 prefix prevents cross-version signature confusion."""
    pae = _build_pae("foo", b"bar")
    assert pae.startswith(b"DSSEv1 ")


def test_pae_handles_empty_payload():
    """Empty payload is valid input (length 0)."""
    pae = _build_pae("application/json", b"")
    assert pae == b"DSSEv1 16 application/json 0 "


def test_pae_handles_utf8_payload_type():
    """payloadType is utf-8 encoded — non-ASCII names work."""
    pae = _build_pae("text/x-é", b"payload")
    # The length is byte-length of UTF-8 encoded string, not char count
    pt_bytes = "text/x-é".encode("utf-8")
    assert str(len(pt_bytes)).encode("ascii") + b" " in pae


# --------------------------------------------------------------------------
# Canonical JSON bytes — must match Ophamin's own canonical form
# --------------------------------------------------------------------------


def test_canonical_json_bytes_sorts_keys():
    """sort_keys=True is load-bearing for byte-level determinism."""
    a = _canonical_json_bytes({"b": 1, "a": 2})
    b = _canonical_json_bytes({"a": 2, "b": 1})
    assert a == b == b'{"a":2,"b":1}'


def test_canonical_json_bytes_tight_separators():
    """No spaces after , or : — matches SCHEMAS.md R1-R11."""
    out = _canonical_json_bytes({"x": [1, 2, 3]})
    assert b", " not in out
    assert b": " not in out


def test_canonical_json_bytes_ensure_ascii():
    """Non-ASCII chars are escaped \\uXXXX — same rule as Ophamin proof
    canonical form (cross-language deserializers need this)."""
    out = _canonical_json_bytes({"k": "héllo"})
    # 'é' must be é-escaped, not raw UTF-8
    assert b"h\\u00e9llo" in out
    assert b"\xc3\xa9" not in out  # raw UTF-8 byte sequence for é


# --------------------------------------------------------------------------
# End-to-end: in-toto Statement signature verifies under inner Ophamin
# verification path. The outer DSSE wraps in-toto; the inner Ophamin HMAC
# on the embedded body MUST still verify under the original Ophamin key
# — that's the load-bearing claim the in-toto layer ships.
# --------------------------------------------------------------------------


def test_inner_ophamin_signature_still_verifies_after_wrapping():
    """The inner Ophamin proof signature is preserved through to_in_toto_statement
    and re-verifies against the embedded predicate.body."""
    ophamin_key = b"ophamin-sign-key"
    proof = _signed_proof(ophamin_key)
    stmt = to_in_toto_statement(proof)

    body = stmt["predicate"]["body"]
    sig = stmt["predicate"]["signature"]

    # Recompute the HMAC the same way EmpiricalProofRecord.sign() does
    from ophamin.measuring.proof.record import _canonical

    expected = hmac.new(
        ophamin_key, _canonical(body).encode("utf-8"), hashlib.sha256
    ).hexdigest()
    assert sig == expected


def test_inner_ophamin_signature_survives_dsse_round_trip():
    """Wrap → DSSE-sign → unwrap → re-verify the inner Ophamin signature."""
    ophamin_key = b"inner-ophamin-key"
    dsse_key = b"outer-dsse-key"

    proof = _signed_proof(ophamin_key)
    env = to_dsse_envelope(proof, dsse_key)

    # Verify DSSE outer
    assert verify_dsse_envelope(env, dsse_key) is True

    # Decode payload back to Statement → predicate.body + predicate.signature
    stmt = json.loads(base64.b64decode(env["payload"]))
    body = stmt["predicate"]["body"]
    sig = stmt["predicate"]["signature"]

    # Verify inner Ophamin HMAC against the body
    from ophamin.measuring.proof.record import _canonical

    expected = hmac.new(
        ophamin_key, _canonical(body).encode("utf-8"), hashlib.sha256
    ).hexdigest()
    assert sig == expected
