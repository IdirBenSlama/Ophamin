"""Demonstrate CR2 — per-author ed25519 attestation, end to end.

The HMAC signature seals integrity under a shared key (anyone with the key can
forge it — not authentication). Attestation adds real, publicly-verifiable
authorship: an author signs with their PRIVATE key; anyone verifies with the
PUBLIC key; an out-of-band registry turns the self-carried key into real
attribution.

This loads the newest proof from the corpus, attests an in-memory copy with a
freshly-generated author key (in a throwaway keystore — the corpus on disk is
not modified), and verifies it three ways. No live substrate needed.

    PYTHONPATH=src .venv/bin/python -u examples/run_attestation_demo.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from ophamin.measuring.proof.attestation import (
    AuthorsRegistry,
    load_or_create_author_key,
)
from ophamin.measuring.proof.codec import iter_proofs
from ophamin.measuring.proof.record import EmpiricalProofRecord


def banner(text: str) -> None:
    print(f"\n{'=' * 72}\n{text}\n{'=' * 72}")


def main() -> int:
    banner("OPHAMIN — CR2: per-author ed25519 attestation")

    proofs = sorted(iter_proofs("proofs"))
    if not proofs:
        print("no proofs in proofs/ — run a scenario first")
        return 1
    proof_path = proofs[-1]
    record = EmpiricalProofRecord.from_dict(
        __import__("json").loads(Path(proof_path).read_text(encoding="utf-8"))
    )
    print(f"proof        : {proof_path}")
    print(f"verdict      : {record.verdict.outcome}")
    print(f"proof_id     : {record.proof_id[:16]}…")
    print(f"hmac signed  : {bool(record.signature)} (integrity seal, shared key)")
    print(f"attested     : {bool(record.attestation)} (before)")

    # A throwaway keystore so the demo never touches the operator's real keys.
    with tempfile.TemporaryDirectory() as ks:
        key = load_or_create_author_key("demo-author", keystore_dir=ks)
        pid_before = record.proof_id
        record.attest(key.private_key, "demo-author")

        banner("ATTESTATION")
        print(f"author       : {record.attestation['author']}")
        print(f"algorithm    : {record.attestation['algorithm']}")
        print(f"public key   : {record.attestation['public_key']}")
        print(f"signature    : {record.attestation['signature'][:32]}…")
        print(f"proof_id kept: {record.proof_id == pid_before} "
              "(attestation lives outside the signed body)")

        banner("VERIFICATION (three ways)")
        print(f"1. self-consistent (embedded key) : "
              f"{record.verify_attestation()}")
        print(f"2. against the correct public key : "
              f"{record.verify_attestation(expected_public_key=key.public_key)}")

        # Real attribution: a registry the verifier trusts, by author NAME.
        registry = AuthorsRegistry({"demo-author": key.public_hex})
        trusted = registry.public_key("demo-author")
        print(f"3. against the authors registry   : "
              f"{record.verify_attestation(expected_public_key=trusted)}")

        # Tamper check — change the verdict and re-verify.
        record.verdict.reasoning = "tampered after attestation"
        print(f"   tampered body now verifies     : "
              f"{record.verify_attestation()}  (expected False)")

    banner("WHAT THIS MEANS")
    print("HMAC = 'did this change?' under a shared key (integrity).")
    print("ed25519 attestation = 'who produced this?' — only the private-key")
    print("holder could sign, and the registry says whose key it is.")
    print("\nSet OPHAMIN_AUTHOR=<you> and every proof you persist is attested.")
    print("Run `ophamin author --author <you> --registry authors.json` to")
    print("publish your public key for others to verify against.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
