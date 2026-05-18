"""Tests for the CloudEvents 1.0 wrapper.

Verifies:
- The wrapper produces a structured-mode envelope with every
  required CloudEvents 1.0 attribute (per §3.1).
- ``wrap`` → ``unwrap`` roundtrips a real Python-emitted signed
  proof byte-for-byte. The unwrapped record still verifies under
  the framework's default sign key (the wrapper does not modify
  the embedded record).
- Extension attribute names follow CloudEvents §3.1's
  ``[a-z0-9]{1,20}`` rule; values are strings.
- Malformed envelopes / malformed proofs raise structured errors,
  not opaque traces.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ophamin import __version__
from ophamin.cloudevents import (
    CLOUDEVENTS_SPEC_VERSION,
    DEFAULT_TYPE,
    OPHAMIN_DATASCHEMA,
    CloudEventEnvelopeError,
    unwrap,
    validate_envelope,
    wrap,
)
from ophamin.interfaces._impls import verify_proof_impl


REPO_ROOT = Path(__file__).resolve().parent.parent
PROOFS_DIR = REPO_ROOT / "proofs" / "measurement_machinery"
ANY_SHIPPED_PROOF = next(PROOFS_DIR.rglob("*.json"), None)


class TestConstants:
    def test_spec_version_is_1_0(self) -> None:
        assert CLOUDEVENTS_SPEC_VERSION == "1.0"

    def test_default_type_follows_reverse_dns_convention(self) -> None:
        # CloudEvents §3.1 recommends reverse-DNS for `type`.
        assert DEFAULT_TYPE.startswith("dev.ophamin.")

    def test_dataschema_points_at_schemas_md(self) -> None:
        assert "SCHEMAS.md" in OPHAMIN_DATASCHEMA
        assert OPHAMIN_DATASCHEMA.startswith("https://")


class TestWrap:
    @pytest.mark.skipif(
        ANY_SHIPPED_PROOF is None,
        reason="no shipped signed proofs found in the repo",
    )
    def test_wrap_real_proof_has_required_attributes(self) -> None:
        proof = json.loads(ANY_SHIPPED_PROOF.read_text(encoding="utf-8"))
        env = wrap(proof, source="urn:test:ophamin")
        # CloudEvents §3.1 REQUIRED attributes
        for required in ("specversion", "id", "source", "type"):
            assert required in env
            assert isinstance(env[required], str)
            assert env[required]
        # Optional but produced by the wrapper
        for produced in (
            "datacontenttype", "dataschema", "time",
            "ophaminversion", "ophaminschema", "ophaminverdict", "data",
        ):
            assert produced in env

    @pytest.mark.skipif(
        ANY_SHIPPED_PROOF is None, reason="no shipped proofs",
    )
    def test_id_matches_proof_id(self) -> None:
        proof = json.loads(ANY_SHIPPED_PROOF.read_text(encoding="utf-8"))
        env = wrap(proof, source="urn:test:ophamin")
        assert env["id"] == proof["proof_id"]

    @pytest.mark.skipif(
        ANY_SHIPPED_PROOF is None, reason="no shipped proofs",
    )
    def test_default_type(self) -> None:
        proof = json.loads(ANY_SHIPPED_PROOF.read_text(encoding="utf-8"))
        env = wrap(proof, source="urn:test:ophamin")
        assert env["type"] == DEFAULT_TYPE

    @pytest.mark.skipif(
        ANY_SHIPPED_PROOF is None, reason="no shipped proofs",
    )
    def test_custom_type(self) -> None:
        proof = json.loads(ANY_SHIPPED_PROOF.read_text(encoding="utf-8"))
        env = wrap(
            proof, source="urn:test:ophamin",
            event_type="dev.ophamin.proof.refuted.v1",
        )
        assert env["type"] == "dev.ophamin.proof.refuted.v1"

    def test_wrap_accepts_dict_str_bytes(self) -> None:
        minimal = {
            "schema_version": "1.0",
            "identity": {"created_at": "2026-05-18T00:00:00+00:00"},
            "verdict": {"outcome": "VALIDATED"},
        }
        as_dict = wrap(minimal, source="urn:test")
        as_str = wrap(json.dumps(minimal), source="urn:test")
        as_bytes = wrap(json.dumps(minimal).encode("utf-8"), source="urn:test")
        # All three produce equivalent envelopes (id is content-addressed
        # over the same body bytes).
        assert as_dict["id"] == as_str["id"] == as_bytes["id"]

    def test_wrap_emits_time_from_identity(self) -> None:
        proof = {
            "schema_version": "1.0",
            "identity": {"created_at": "2026-05-18T12:34:56+00:00"},
        }
        env = wrap(proof, source="urn:test")
        assert env["time"] == "2026-05-18T12:34:56+00:00"

    def test_wrap_emits_verdict_outcome(self) -> None:
        for outcome in ("VALIDATED", "REFUTED", "INCONCLUSIVE"):
            env = wrap(
                {"schema_version": "1.0", "verdict": {"outcome": outcome}},
                source="urn:test",
            )
            assert env["ophaminverdict"] == outcome

    def test_wrap_emits_framework_version_when_record_missing_it(self) -> None:
        env = wrap({"schema_version": "1.0"}, source="urn:test")
        assert env["ophaminversion"] == __version__

    def test_extension_attribute_name_must_be_lowercase_alphanumeric(
        self,
    ) -> None:
        with pytest.raises(CloudEventEnvelopeError, match="3.1"):
            wrap(
                {"schema_version": "1.0"},
                source="urn:test",
                extra_extensions={"Bad-Name": "x"},
            )

    def test_extension_attribute_name_too_long(self) -> None:
        with pytest.raises(CloudEventEnvelopeError):
            wrap(
                {"schema_version": "1.0"},
                source="urn:test",
                extra_extensions={"a" * 21: "x"},
            )

    def test_extension_attribute_value_must_be_string(self) -> None:
        with pytest.raises(CloudEventEnvelopeError, match="must be a string"):
            wrap(
                {"schema_version": "1.0"},
                source="urn:test",
                extra_extensions={"valid": 42},  # type: ignore[dict-item]
            )

    def test_extension_attribute_cannot_collide_with_builtin(self) -> None:
        with pytest.raises(CloudEventEnvelopeError, match="collides"):
            wrap(
                {"schema_version": "1.0"},
                source="urn:test",
                extra_extensions={"data": "should-fail"},
            )

    def test_extension_attribute_accepted_when_valid(self) -> None:
        env = wrap(
            {"schema_version": "1.0"},
            source="urn:test",
            extra_extensions={"trace": "abc123", "deployment": "prod"},
        )
        assert env["trace"] == "abc123"
        assert env["deployment"] == "prod"

    def test_wrap_requires_source(self) -> None:
        with pytest.raises(CloudEventEnvelopeError, match="source"):
            wrap({"schema_version": "1.0"}, source="")

    def test_wrap_rejects_non_dict_proof(self) -> None:
        with pytest.raises(CloudEventEnvelopeError):
            wrap(42, source="urn:test")  # type: ignore[arg-type]

    def test_wrap_rejects_invalid_proof_json(self) -> None:
        with pytest.raises(CloudEventEnvelopeError, match="parse"):
            wrap("not json", source="urn:test")


class TestUnwrap:
    @pytest.mark.skipif(
        ANY_SHIPPED_PROOF is None, reason="no shipped proofs",
    )
    def test_roundtrip_preserves_proof_byte_for_byte(self) -> None:
        proof = json.loads(ANY_SHIPPED_PROOF.read_text(encoding="utf-8"))
        env = wrap(proof, source="urn:test")
        recovered = unwrap(env)
        assert recovered == proof

    @pytest.mark.skipif(
        ANY_SHIPPED_PROOF is None, reason="no shipped proofs",
    )
    def test_unwrapped_proof_still_verifies(self) -> None:
        """A wrapped+unwrapped proof still verifies under the
        framework's default key. The wrapper does not modify the
        embedded record.
        """
        proof = json.loads(ANY_SHIPPED_PROOF.read_text(encoding="utf-8"))
        env = wrap(proof, source="urn:test")
        recovered = unwrap(env)
        result = verify_proof_impl(json.dumps(recovered))
        assert result["verified"] is True

    def test_unwrap_accepts_dict_str_bytes(self) -> None:
        env_dict = wrap({"schema_version": "1.0"}, source="urn:test")
        as_dict = unwrap(env_dict)
        as_str = unwrap(json.dumps(env_dict))
        as_bytes = unwrap(json.dumps(env_dict).encode("utf-8"))
        assert as_dict == as_str == as_bytes

    def test_unwrap_rejects_missing_required_attribute(self) -> None:
        broken = {"specversion": "1.0", "id": "abc", "source": "urn:test"}
        # Missing `type`
        with pytest.raises(CloudEventEnvelopeError, match="type"):
            unwrap(broken)

    def test_unwrap_rejects_wrong_spec_version(self) -> None:
        broken = {
            "specversion": "0.3",  # not 1.0
            "id": "abc",
            "source": "urn:test",
            "type": "x",
            "data": {},
        }
        with pytest.raises(CloudEventEnvelopeError, match="specversion"):
            unwrap(broken)

    def test_unwrap_rejects_non_object_data(self) -> None:
        broken = {
            "specversion": "1.0",
            "id": "abc",
            "source": "urn:test",
            "type": "x",
            "data": "not an object",
        }
        with pytest.raises(CloudEventEnvelopeError, match="data"):
            unwrap(broken)

    def test_unwrap_rejects_malformed_json(self) -> None:
        with pytest.raises(CloudEventEnvelopeError, match="parse"):
            unwrap("not json")

    def test_unwrap_rejects_non_dict_envelope_text(self) -> None:
        with pytest.raises(CloudEventEnvelopeError, match="JSON object"):
            unwrap("[1, 2, 3]")


class TestValidateEnvelope:
    def test_valid_envelope_passes(self) -> None:
        env = wrap({"schema_version": "1.0"}, source="urn:test")
        validate_envelope(env)  # no raise

    def test_missing_id(self) -> None:
        with pytest.raises(CloudEventEnvelopeError, match="id"):
            validate_envelope({
                "specversion": "1.0",
                "source": "urn:test",
                "type": "x",
            })

    def test_empty_required_attribute(self) -> None:
        with pytest.raises(CloudEventEnvelopeError, match="empty"):
            validate_envelope({
                "specversion": "1.0",
                "id": "",
                "source": "urn:test",
                "type": "x",
            })


class TestInteropAcrossOphaminLayers:
    """The wrap/unwrap path composes cleanly with the other interop
    surfaces."""

    @pytest.mark.skipif(
        ANY_SHIPPED_PROOF is None, reason="no shipped proofs",
    )
    def test_wrap_then_verify_via_http_impl(self) -> None:
        """A proof wrapped in CloudEvents → unwrapped → verified
        through the shared HTTP/MCP verify impl works end-to-end."""
        proof_text = ANY_SHIPPED_PROOF.read_text(encoding="utf-8")
        env = wrap(proof_text, source="urn:test:integration")
        recovered = unwrap(env)
        result = verify_proof_impl(json.dumps(recovered))
        assert result["verified"] is True
        assert result["proof_id"] == env["id"]
