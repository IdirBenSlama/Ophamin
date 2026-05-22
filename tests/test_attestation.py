"""Tests for CR2 — per-author ed25519 attestation.

The HMAC ``signature`` is a shared-key integrity seal (tamper-evident, not
authenticating). Attestation adds real, publicly-verifiable authorship:

  * primitives — keygen / sign / verify; wrong-length keys raise; bad sig is
    a clean False, never a crash
  * keystore — per-author private keys created at mode 0600, reloaded stably,
    env-overridable, loud on corruption; private keys never in the repo tree
  * registry — the out-of-band trust anchor that turns a self-carried key into
    real attribution
  * record — attest/verify round-trip, tamper detection, wrong-expected-key
    rejection, backward-compatible serialization + schema
"""

from __future__ import annotations

import json
import os
import stat

import pytest

from ophamin.measuring.proof.attestation import (
    AttestationError,
    AuthorsRegistry,
    KeystoreError,
    from_hex,
    generate_private_key,
    load_or_create_author_key,
    public_key_for,
    sign_bytes,
    verify_bytes,
)
from ophamin.measuring.proof.codec import validate_schema
from ophamin.measuring.proof.record import EmpiricalProofRecord

from tests.test_proof_codec import _TEST_KEY, _make_record


# --- primitives ------------------------------------------------------------


class TestPrimitives:
    def test_keygen_lengths(self):
        priv = generate_private_key()
        assert len(priv) == 32
        assert len(public_key_for(priv)) == 32

    def test_distinct_keys(self):
        assert generate_private_key() != generate_private_key()

    def test_public_key_is_deterministic(self):
        priv = generate_private_key()
        assert public_key_for(priv) == public_key_for(priv)

    def test_sign_verify_round_trip(self):
        priv = generate_private_key()
        pub = public_key_for(priv)
        msg = b"the proof body"
        sig = sign_bytes(priv, msg)
        assert len(sig) == 64
        assert verify_bytes(pub, msg, sig) is True

    def test_verify_rejects_tampered_message(self):
        priv = generate_private_key()
        pub = public_key_for(priv)
        sig = sign_bytes(priv, b"original")
        assert verify_bytes(pub, b"tampered", sig) is False

    def test_verify_rejects_wrong_key(self):
        priv = generate_private_key()
        sig = sign_bytes(priv, b"msg")
        other_pub = public_key_for(generate_private_key())
        assert verify_bytes(other_pub, b"msg", sig) is False

    def test_verify_bad_signature_length_is_false_not_crash(self):
        pub = public_key_for(generate_private_key())
        assert verify_bytes(pub, b"msg", b"too-short") is False

    def test_wrong_length_private_key_raises(self):
        with pytest.raises(AttestationError):
            sign_bytes(b"short", b"msg")

    def test_wrong_length_public_key_raises(self):
        with pytest.raises(AttestationError):
            verify_bytes(b"short", b"msg", b"x" * 64)

    def test_from_hex_rejects_garbage(self):
        with pytest.raises(AttestationError):
            from_hex("not-hex-zz")


# --- keystore --------------------------------------------------------------


class TestKeystore:
    def test_create_then_reload_is_stable(self, tmp_path, monkeypatch):
        monkeypatch.delenv("OPHAMIN_SIGNING_KEY", raising=False)
        k1 = load_or_create_author_key("idir", keystore_dir=tmp_path)
        k2 = load_or_create_author_key("idir", keystore_dir=tmp_path)
        assert k1.private_key == k2.private_key
        assert k1.public_key == k2.public_key
        assert k1.author == "idir"

    def test_private_key_file_is_0600(self, tmp_path, monkeypatch):
        monkeypatch.delenv("OPHAMIN_SIGNING_KEY", raising=False)
        load_or_create_author_key("idir", keystore_dir=tmp_path)
        keyfile = tmp_path / "idir.ed25519.key"
        assert keyfile.exists()
        mode = stat.S_IMODE(os.stat(keyfile).st_mode)
        assert mode == 0o600, f"private key must be 0600, got {oct(mode)}"

    def test_private_key_filename_is_gitignored_extension(self, tmp_path, monkeypatch):
        # *.key is in .gitignore; the keystore must use that extension so a
        # private key can never be accidentally committed.
        monkeypatch.delenv("OPHAMIN_SIGNING_KEY", raising=False)
        load_or_create_author_key("idir", keystore_dir=tmp_path)
        assert (tmp_path / "idir.ed25519.key").exists()

    def test_distinct_authors_distinct_keys(self, tmp_path, monkeypatch):
        monkeypatch.delenv("OPHAMIN_SIGNING_KEY", raising=False)
        a = load_or_create_author_key("alice", keystore_dir=tmp_path)
        b = load_or_create_author_key("bob", keystore_dir=tmp_path)
        assert a.private_key != b.private_key

    def test_env_override(self, tmp_path, monkeypatch):
        priv = generate_private_key()
        monkeypatch.setenv("OPHAMIN_SIGNING_KEY", priv.hex())
        k = load_or_create_author_key("idir", keystore_dir=tmp_path)
        assert k.private_key == priv
        # env path must not write a keystore file
        assert not (tmp_path / "idir.ed25519.key").exists()

    def test_env_override_bad_length_raises(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPHAMIN_SIGNING_KEY", (b"x" * 8).hex())
        with pytest.raises(KeystoreError):
            load_or_create_author_key("idir", keystore_dir=tmp_path)

    def test_empty_author_raises(self, tmp_path, monkeypatch):
        monkeypatch.delenv("OPHAMIN_SIGNING_KEY", raising=False)
        with pytest.raises(KeystoreError):
            load_or_create_author_key("   ", keystore_dir=tmp_path)

    def test_corrupt_keystore_file_raises_loud(self, tmp_path, monkeypatch):
        monkeypatch.delenv("OPHAMIN_SIGNING_KEY", raising=False)
        (tmp_path / "idir.ed25519.key").write_text("not-a-key", encoding="ascii")
        with pytest.raises(KeystoreError):
            load_or_create_author_key("idir", keystore_dir=tmp_path)


# --- authors registry ------------------------------------------------------


class TestRegistry:
    def test_trusts_registered_key(self):
        pub = public_key_for(generate_private_key())
        reg = AuthorsRegistry({"idir": pub.hex()})
        assert reg.trusts("idir", pub) is True
        assert reg.public_key("idir") == pub

    def test_does_not_trust_unregistered_or_wrong(self):
        pub = public_key_for(generate_private_key())
        reg = AuthorsRegistry({"idir": pub.hex()})
        assert reg.trusts("eve", pub) is False
        assert reg.trusts("idir", public_key_for(generate_private_key())) is False

    def test_from_file_round_trip(self, tmp_path):
        pub = public_key_for(generate_private_key())
        p = tmp_path / "authors.json"
        p.write_text(json.dumps({"idir": pub.hex()}), encoding="utf-8")
        reg = AuthorsRegistry.from_file(p)
        assert reg.trusts("idir", pub)

    def test_from_file_missing_raises(self, tmp_path):
        with pytest.raises(KeystoreError):
            AuthorsRegistry.from_file(tmp_path / "nope.json")

    def test_from_file_bad_pubkey_raises(self, tmp_path):
        p = tmp_path / "authors.json"
        p.write_text(json.dumps({"idir": "deadbeef"}), encoding="utf-8")
        with pytest.raises(KeystoreError):
            AuthorsRegistry.from_file(p)


# --- record attest / verify ------------------------------------------------


class TestRecordAttestation:
    def test_attest_then_verify(self):
        rec = _make_record().sign(_TEST_KEY)
        priv = generate_private_key()
        rec.attest(priv, "idir")
        assert rec.verify_attestation() is True
        assert rec.attestation["author"] == "idir"
        assert rec.attestation["algorithm"] == "ed25519"

    def test_verify_with_expected_key(self):
        rec = _make_record().sign(_TEST_KEY)
        priv = generate_private_key()
        pub = public_key_for(priv)
        rec.attest(priv, "idir")
        assert rec.verify_attestation(expected_public_key=pub) is True
        other = public_key_for(generate_private_key())
        assert rec.verify_attestation(expected_public_key=other) is False

    def test_attest_does_not_break_hmac(self):
        rec = _make_record().sign(_TEST_KEY)
        rec.attest(generate_private_key(), "idir")
        assert rec.verify_signature(_TEST_KEY) is True

    def test_tampered_body_fails_attestation(self):
        rec = _make_record().sign(_TEST_KEY)
        rec.attest(generate_private_key(), "idir")
        rec.verdict.reasoning = "tampered after attest"
        assert rec.verify_attestation() is False

    def test_unattested_record_verify_is_false(self):
        rec = _make_record().sign(_TEST_KEY)
        assert rec.attestation == {}
        assert rec.verify_attestation() is False

    def test_empty_author_raises(self):
        rec = _make_record().sign(_TEST_KEY)
        with pytest.raises(ValueError):
            rec.attest(generate_private_key(), "")

    def test_serialization_round_trip(self):
        rec = _make_record().sign(_TEST_KEY)
        priv = generate_private_key()
        pub = public_key_for(priv)
        rec.attest(priv, "idir")
        d = rec.to_dict()
        assert "attestation" in d
        rt = EmpiricalProofRecord.from_dict(d)
        assert rt.verify_attestation(expected_public_key=pub) is True

    def test_unattested_to_dict_omits_attestation(self):
        # backward compat: un-attested proofs must not gain an attestation key
        rec = _make_record().sign(_TEST_KEY)
        d = rec.to_dict()
        assert "attestation" not in d

    def test_attested_proof_is_schema_valid(self, tmp_path):
        rec = _make_record().sign(_TEST_KEY)
        rec.attest(generate_private_key(), "idir")
        p = tmp_path / "attested.json"
        p.write_text(json.dumps(rec.to_dict()), encoding="utf-8")
        ok, errors = validate_schema(p)
        assert ok, errors

    def test_unattested_proof_still_schema_valid(self, tmp_path):
        rec = _make_record().sign(_TEST_KEY)
        p = tmp_path / "plain.json"
        p.write_text(json.dumps(rec.to_dict()), encoding="utf-8")
        ok, errors = validate_schema(p)
        assert ok, errors

    def test_proof_id_unchanged_by_attestation(self):
        # attestation lives outside the body, so it must NOT change proof_id
        rec = _make_record().sign(_TEST_KEY)
        pid_before = rec.proof_id
        rec.attest(generate_private_key(), "idir")
        assert rec.proof_id == pid_before


# --- persist-time opt-in attestation ---------------------------------------


class TestPersistAttestation:
    """persist_proof attests automatically when OPHAMIN_AUTHOR is set —
    centralized so every scenario gets attestation with zero per-scenario code,
    and backward-compatible (no author -> un-attested)."""

    def _persist(self, tmp_path):
        from ophamin.measuring.proof.persistence import BundleFormat, persist_proof

        rec = _make_record().sign(_TEST_KEY)
        return persist_proof(
            rec, root=tmp_path / "proofs", tier="scientific",
            scenario_name="attest-test", formats=BundleFormat.json_only(),
        )

    def test_attests_when_author_configured(self, tmp_path, monkeypatch):
        monkeypatch.delenv("OPHAMIN_SIGNING_KEY", raising=False)
        monkeypatch.setenv("OPHAMIN_AUTHOR", "idir")
        monkeypatch.setenv("OPHAMIN_KEYSTORE", str(tmp_path / "ks"))
        bundle = self._persist(tmp_path)
        data = json.loads((bundle.bundle_dir / "proof.json").read_text())
        assert data.get("attestation", {}).get("author") == "idir"
        rt = EmpiricalProofRecord.from_dict(data)
        key = load_or_create_author_key("idir", keystore_dir=tmp_path / "ks")
        assert rt.verify_attestation(expected_public_key=key.public_key) is True

    def test_no_author_means_unattested(self, tmp_path, monkeypatch):
        monkeypatch.delenv("OPHAMIN_AUTHOR", raising=False)
        monkeypatch.delenv("OPHAMIN_SIGNING_KEY", raising=False)
        bundle = self._persist(tmp_path)
        data = json.loads((bundle.bundle_dir / "proof.json").read_text())
        assert "attestation" not in data

    def test_private_key_never_in_written_proof(self, tmp_path, monkeypatch):
        monkeypatch.delenv("OPHAMIN_SIGNING_KEY", raising=False)
        monkeypatch.setenv("OPHAMIN_AUTHOR", "idir")
        monkeypatch.setenv("OPHAMIN_KEYSTORE", str(tmp_path / "ks"))
        bundle = self._persist(tmp_path)
        key = load_or_create_author_key("idir", keystore_dir=tmp_path / "ks")
        text = (bundle.bundle_dir / "proof.json").read_text()
        assert key.private_key.hex() not in text


# --- author CLI ------------------------------------------------------------


class TestAuthorCLI:
    def test_keygen_prints_public_key_and_writes_registry(
        self, tmp_path, monkeypatch, capsys
    ):
        from ophamin.cli import build_parser

        monkeypatch.delenv("OPHAMIN_SIGNING_KEY", raising=False)
        ks = tmp_path / "ks"
        reg = tmp_path / "authors.json"
        args = build_parser().parse_args(
            ["author", "--author", "idir",
             "--keystore", str(ks), "--registry", str(reg)]
        )
        rc = args.func(args)
        assert rc == 0
        out = capsys.readouterr().out
        assert "public key" in out
        # registry written with the author's public key (committable)
        data = json.loads(reg.read_text())
        key = load_or_create_author_key("idir", keystore_dir=ks)
        assert data["idir"] == key.public_hex
        # private key never printed
        assert key.private_key.hex() not in out

    def test_empty_author_is_error(self, tmp_path, monkeypatch):
        from ophamin.cli import build_parser

        monkeypatch.delenv("OPHAMIN_SIGNING_KEY", raising=False)
        args = build_parser().parse_args(
            ["author", "--author", "   ", "--keystore", str(tmp_path / "ks")]
        )
        assert args.func(args) == 2


# --- verify surface (HTTP/Console verify_proof_impl) ------------------------


class TestVerifyImplAttestation:
    """The cross-surface verify path must report attestation AND keep HMAC
    verification correct when an attestation block is present — attestation is
    outside the signed body, so it must be excluded from the HMAC recompute."""

    def _b64key(self):
        import base64

        return base64.b64encode(_TEST_KEY).decode()

    def test_attested_proof_verifies_both_layers(self):
        import json as _json

        from ophamin.interfaces._impls import verify_proof_impl

        rec = _make_record().sign(_TEST_KEY)
        rec.attest(generate_private_key(), "idir")
        res = verify_proof_impl(_json.dumps(rec.to_dict()), self._b64key())
        assert res["verified"] is True  # HMAC not broken by the attestation block
        assert res["attested"] is True
        assert res["attestation_author"] == "idir"
        assert res["attestation_verified"] is True

    def test_unattested_proof_reports_not_attested(self):
        import json as _json

        from ophamin.interfaces._impls import verify_proof_impl

        rec = _make_record().sign(_TEST_KEY)
        res = verify_proof_impl(_json.dumps(rec.to_dict()), self._b64key())
        assert res["verified"] is True
        assert res["attested"] is False
        assert res["attestation_verified"] is False

    def test_tampered_attested_proof_fails_both(self):
        import json as _json

        from ophamin.interfaces._impls import verify_proof_impl

        rec = _make_record().sign(_TEST_KEY)
        rec.attest(generate_private_key(), "idir")
        d = rec.to_dict()
        d["verdict"]["reasoning"] = "tampered"
        res = verify_proof_impl(_json.dumps(d), self._b64key())
        assert res["verified"] is False
        assert res["attestation_verified"] is False
