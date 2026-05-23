"""Track 2: ed25519 attestation is ON BY DEFAULT in persist_proof.

Pins:
- A real proof (OPHAMIN_ATTEST != 0) carries a verifiable ed25519 attestation.
- OPHAMIN_ATTEST=0 opts out (deterministic, un-attested) — what the suite uses.
- Attestation does NOT change proof_id (it lives outside the signed body).
- Registry attribution: verify against the right public key passes, wrong fails.

The HMAC signature is integrity-only (a shared key anyone can forge); the point
of attestation is that ANYONE can verify authorship with the public key — no
trust in the framework required.
"""

from __future__ import annotations

import json
from pathlib import Path

from ophamin.measuring.proof import (
    BundleFormat,
    Claim,
    DatasetRef,
    EmpiricalProofRecord,
    PillarEvidence,
    PreRegistration,
    Reproduction,
    Threshold,
    Verdict,
    content_hash,
    persist_proof,
)
from ophamin.measuring.proof.attestation import (
    AuthorsRegistry,
    generate_private_key,
    public_key_for,
)
from ophamin.measuring.proof.persistence import _default_author


def _record() -> EmpiricalProofRecord:
    threshold = Threshold(metric="x", comparator=">=", value=1.0)
    claim = Claim(statement="Test.", operationalization="noop",
                  threshold=threshold, h0="h0", h1="h1")
    prereg = PreRegistration(
        config_hash=content_hash({"x": 1}), data_hash=content_hash({"y": 2}),
        analysis_plan="noop")
    dataset = DatasetRef(name="ds", content_hash=content_hash({"d": 1}),
                         n_records=1, source="synthetic", kind="test")
    evidence = [PillarEvidence(pillar="t", statistic_name="x", statistic_value=1.0,
                               library="stdlib", library_version="1.0")]
    record = EmpiricalProofRecord(
        claim=claim, preregistration=prereg, datasets=[dataset],
        substrate_name="mock", substrate_git_commit="d" * 40, evidence=evidence,
        verdict=Verdict.decide(observed=1.0, threshold=threshold),
        reproduction=Reproduction(command="echo run"),
        ophamin_version="0.0.0", ophamin_git_commit="c" * 40,
    )
    record.sign(b"test-key")
    return record


def _proof_json(root: Path) -> dict:
    jpath = next(Path(root).rglob("proof.json"))
    return json.loads(jpath.read_text(encoding="utf-8"))


class TestDefaultOn:
    def test_attested_by_default(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPHAMIN_ATTEST", "1")
        monkeypatch.setenv("OPHAMIN_AUTHOR", "test-author")
        monkeypatch.setenv("OPHAMIN_KEYSTORE", str(tmp_path / "keys"))
        rec = _record()
        pid_before = rec.proof_id
        persist_proof(rec, root=tmp_path / "proofs", tier="scientific",
                      scenario_name="t", formats=BundleFormat.json_only())
        data = _proof_json(tmp_path / "proofs")
        assert data.get("attestation"), "expected an attestation block by default"
        assert data["attestation"]["author"] == "test-author"
        assert data["attestation"]["algorithm"] == "ed25519"
        # proof_id is unchanged — attestation lives outside the signed body
        assert rec.proof_id == pid_before
        # the embedded signature actually verifies
        loaded = EmpiricalProofRecord.from_dict(data)
        assert loaded.verify_attestation() is True

    def test_opt_out_is_unattested(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPHAMIN_ATTEST", "0")
        monkeypatch.setenv("OPHAMIN_KEYSTORE", str(tmp_path / "keys"))
        rec = _record()
        persist_proof(rec, root=tmp_path / "proofs", tier="scientific",
                      scenario_name="t", formats=BundleFormat.json_only())
        data = _proof_json(tmp_path / "proofs")
        assert not data.get("attestation")

    def test_default_author_nonempty(self):
        assert _default_author().strip()


class TestRegistryAttribution:
    def test_right_key_attributes_wrong_key_does_not(self):
        priv = generate_private_key()
        pub = public_key_for(priv)
        rec = _record()
        rec.attest(priv, "alice", public_key=pub)
        # self-carried signature verifies (integrity + non-repudiation)
        assert rec.verify_attestation() is True
        # attribution: matches the registered key -> trusted
        registry = AuthorsRegistry({"alice": pub.hex()})
        assert rec.verify_attestation(expected_public_key=registry.public_key("alice")) is True
        # a different key -> NOT attributed
        other_pub = public_key_for(generate_private_key())
        assert rec.verify_attestation(expected_public_key=other_pub) is False

    def test_tampered_body_breaks_attestation(self):
        priv = generate_private_key()
        rec = _record()
        rec.attest(priv, "alice")
        assert rec.verify_attestation() is True
        rec.substrate_name = "tampered"  # mutate the body after signing
        assert rec.verify_attestation() is False
