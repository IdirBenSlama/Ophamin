"""Per-author ed25519 attestation for Ophamin proof records.

The proof record's HMAC ``signature`` (``base.DEFAULT_SIGN_KEY``) is a
content-*integrity* seal: it detects tampering **within a trust boundary**
where the key is shared. It is NOT authentication — anyone who knows the
shared key can forge a "valid" signature. That is fine for "did this file
change?" and wrong for "*who* produced this proof?".

Attestation answers the second question with public-key cryptography. An
author signs the proof body with their ed25519 **private** key; anyone
verifies with the author's **public** key. Three honest properties:

  * **Integrity** — the body cannot change without breaking the signature.
  * **Non-repudiation** — only the holder of the private key could have
    produced the signature.
  * **Attribution** — *iff* the verifier knows the author's true public key
    (from an out-of-band registry, not the proof itself), the signature
    proves WHO.

The public key travels inside the proof for convenience, but a proof that
carries its own key only proves "the holder of THIS key signed it" — an
attacker can re-sign with their own keypair and stamp any author string.
Real attribution requires checking the embedded key against a trusted
registry (:class:`AuthorsRegistry`); ``verify_attestation(expected_public_key
=...)`` on the record does exactly that. We do not pretend the embedded key
alone is attribution — that honesty is the point of CR2.

Private keys NEVER enter the repo. They live in a keystore (default
``~/.ophamin/keys/<author>.ed25519.key``, mode 0600) or an env var
(``OPHAMIN_SIGNING_KEY``, hex). Only public keys are shareable / committable.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

ALGORITHM = "ed25519"
_PRIV_LEN = 32  # ed25519 raw private key length
_PUB_LEN = 32  # ed25519 raw public key length
_SIG_LEN = 64  # ed25519 signature length


class AttestationError(RuntimeError):
    """A cryptographic precondition was violated (bad key/sig length etc.)."""


class KeystoreError(RuntimeError):
    """A keystore / authors-registry file is missing or malformed."""


# --- raw ed25519 primitives ------------------------------------------------


def _require_len(name: str, b: bytes, n: int) -> None:
    if not isinstance(b, (bytes, bytearray)):
        raise AttestationError(f"{name} must be raw bytes, got {type(b).__name__}")
    if len(b) != n:
        raise AttestationError(f"{name} must be {n} raw bytes, got {len(b)}")


def generate_private_key() -> bytes:
    """A fresh ed25519 private key as 32 raw bytes."""
    return Ed25519PrivateKey.generate().private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )


def public_key_for(private_bytes: bytes) -> bytes:
    """The 32-byte public key for a 32-byte private key."""
    _require_len("private key", private_bytes, _PRIV_LEN)
    pub = Ed25519PrivateKey.from_private_bytes(bytes(private_bytes)).public_key()
    return pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def sign_bytes(private_bytes: bytes, message: bytes) -> bytes:
    """ed25519 signature (64 bytes) over ``message`` with ``private_bytes``."""
    _require_len("private key", private_bytes, _PRIV_LEN)
    return Ed25519PrivateKey.from_private_bytes(bytes(private_bytes)).sign(message)


def verify_bytes(public_bytes: bytes, message: bytes, signature: bytes) -> bool:
    """True iff ``signature`` is a valid ed25519 signature over ``message``.

    Returns ``False`` on a bad signature (never raises for that) but raises
    :class:`AttestationError` on a malformed public key — a wrong-length key
    is a programming error, not a failed verification.
    """
    _require_len("public key", public_bytes, _PUB_LEN)
    if not isinstance(signature, (bytes, bytearray)) or len(signature) != _SIG_LEN:
        return False
    try:
        Ed25519PublicKey.from_public_bytes(bytes(public_bytes)).verify(
            bytes(signature), message
        )
        return True
    except InvalidSignature:
        return False


def to_hex(b: bytes) -> str:
    return bytes(b).hex()


def from_hex(s: str) -> bytes:
    try:
        return bytes.fromhex(s)
    except (ValueError, TypeError) as exc:
        raise AttestationError(f"not valid hex: {exc}") from exc


# --- per-author keystore ---------------------------------------------------


def default_keystore_dir() -> Path:
    """Where private keys live. ``OPHAMIN_KEYSTORE`` overrides; default is the
    user-home ``~/.ophamin/keys`` so private keys are never inside the repo."""
    env = os.environ.get("OPHAMIN_KEYSTORE")
    return Path(env) if env else Path.home() / ".ophamin" / "keys"


def _slug(author: str) -> str:
    return "".join(c if (c.isalnum() or c in "-_.") else "_" for c in author.strip())


@dataclass(frozen=True)
class AuthorKey:
    """An author's keypair. ``private_key`` never leaves the process / keystore."""

    author: str
    private_key: bytes  # 32 raw bytes — never serialized into a proof or the repo
    public_key: bytes  # 32 raw bytes — shareable

    @property
    def public_hex(self) -> str:
        return self.public_key.hex()


def _read_private_key_file(path: Path) -> bytes:
    raw = path.read_bytes().strip()
    try:
        priv = bytes.fromhex(raw.decode("ascii"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise KeystoreError(
            f"keystore file {path} is not a hex-encoded ed25519 key: {exc}"
        ) from exc
    if len(priv) != _PRIV_LEN:
        raise KeystoreError(
            f"keystore file {path} is not a 32-byte ed25519 key (got {len(priv)})"
        )
    return priv


def load_or_create_author_key(
    author: str, keystore_dir: str | Path | None = None
) -> AuthorKey:
    """Load ``author``'s private key from the keystore, creating it if absent.

    Resolution order:
      1. ``OPHAMIN_SIGNING_KEY`` env var (hex private key) — ephemeral / CI use.
      2. ``<keystore_dir>/<author>.ed25519.key`` — created at mode 0600 if
         missing (gitignored by the ``*.key`` rule; never committed).

    Raises :class:`KeystoreError` on an empty author or a malformed key file —
    loud failure, never a silent fresh key over a corrupt one.
    """
    if not author or not author.strip():
        raise KeystoreError("author must be a non-empty string")

    env_priv = os.environ.get("OPHAMIN_SIGNING_KEY")
    if env_priv and env_priv.strip():
        priv = from_hex(env_priv.strip())
        if len(priv) != _PRIV_LEN:
            raise KeystoreError(
                "OPHAMIN_SIGNING_KEY is not a 32-byte ed25519 key "
                f"(got {len(priv)} bytes)"
            )
        return AuthorKey(author, priv, public_key_for(priv))

    d = Path(keystore_dir) if keystore_dir else default_keystore_dir()
    path = d / f"{_slug(author)}.ed25519.key"
    if path.exists():
        priv = _read_private_key_file(path)
    else:
        d.mkdir(parents=True, exist_ok=True)
        priv = generate_private_key()
        path.write_text(priv.hex(), encoding="ascii")
        os.chmod(path, 0o600)
    return AuthorKey(author, priv, public_key_for(priv))


# --- authors registry (the out-of-band trust anchor) -----------------------


@dataclass(frozen=True)
class AuthorsRegistry:
    """Maps an author NAME to the public key the verifier trusts for them.

    This is the out-of-band trust anchor that turns a self-carried attestation
    into real attribution: ``record.verify_attestation(expected_public_key=
    registry.public_key(author))``. The registry holds only PUBLIC keys, so it
    is safe to commit / share. Without it, an attestation proves only that the
    holder of the embedded key signed — not that the key belongs to the named
    author.
    """

    keys: dict[str, str]  # author -> public-key hex

    @classmethod
    def from_file(cls, path: str | Path) -> "AuthorsRegistry":
        p = Path(path)
        if not p.exists():
            raise KeystoreError(f"authors registry not found: {p}")
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            raise KeystoreError(f"authors registry {p} is unreadable: {exc}") from exc
        if not isinstance(data, dict):
            raise KeystoreError("authors registry must be a JSON object")
        keys: dict[str, str] = {}
        for author, pub_hex in data.items():
            if not isinstance(pub_hex, str) or len(from_hex(pub_hex)) != _PUB_LEN:
                raise KeystoreError(
                    f"author {author!r} has an invalid ed25519 public key"
                )
            keys[str(author)] = pub_hex
        return cls(keys)

    def public_key(self, author: str) -> bytes | None:
        k = self.keys.get(author)
        return from_hex(k) if k else None

    def trusts(self, author: str, public_bytes: bytes) -> bool:
        """True iff ``public_bytes`` is the registered key for ``author``."""
        k = self.public_key(author)
        return k is not None and k == bytes(public_bytes)
