# `crates/` — Rust read-only signed-record codecs (RFC 0002 Phase E9)

> **Status:** queued / scaffolding only. The Rust crate hasn't been
> authored yet — this directory holds the future home of
> `ophamin-proof`, the Rust read-only verifier for Ophamin's signed
> `EmpiricalProofRecord` schema.

## Why a Rust crate

[RFC 0002 §3.1 Phase E9](https://github.com/IdirBenSlama/Ophamin/blob/main/docs/rfc/0002-sota-elevation-stages-5-and-6.md)
names cross-language interop as the engineering-tier capstone of
the elevation arc:

> SOTA scientific frameworks have at minimum a Read API in adjacent
> languages. Concrete shape:
>
> * **Rust signed-record codec** (read-only) — a `cargo` crate
>   `ophamin-proof` that parses `EmpiricalProofRecord` JSON, verifies
>   the signature, and exposes the data structurally. Validates the
>   schema is platform-agnostic; opens the door to Rust scenarios.
> * **JS / TypeScript signed-record codec** — same pattern, for the
>   browser-side replay-a-proof story.
> * **Schema stability via cross-language tests** — the Rust + JS
>   codecs run against a fixture of 100 signed proofs from Python;
>   byte-equal signature verification across all three.

## What the crate will provide

```text
crates/ophamin-proof/
├── Cargo.toml          — crate manifest
├── src/
│   └── lib.rs          — public API: deserialize + verify
├── tests/
│   └── verify_python_proofs.rs
│                       — load every proof under proofs/ and
│                         verify the HMAC matches the Python
│                         codec byte-for-byte
└── README.md           — usage + verification protocol
```

Public API (planned):

```rust
pub fn parse_proof(json_bytes: &[u8]) -> Result<EmpiricalProofRecord, ParseError>;

pub fn verify_signature(record: &EmpiricalProofRecord, key: &[u8]) -> bool;

pub fn canonical_body_bytes(record: &EmpiricalProofRecord) -> Vec<u8>;
```

## Why scaffolding only

`cargo` is not present in this development environment. Shipping
Rust source without local compile + test capability would risk
silently-broken code. The crate will land in a follow-on session
that has `cargo` installed.

The remaining work to ship Phase E9.1:

1. Author `Cargo.toml` + `src/lib.rs` + `tests/verify_python_proofs.rs`.
2. Add a `.github/workflows/rust.yml` workflow that installs the
   Rust toolchain (via `dtolnay/rust-toolchain@stable`) and runs
   `cargo test --workspace`.
3. Pin a byte-equality assertion: every shipped Python proof
   under `proofs/` verifies cleanly under the Rust crate using the
   same `DEFAULT_SIGN_KEY`.
4. Document the canonical-body byte representation in `SCHEMAS.md`
   (currently informally documented in `record.py`'s `_canonical`
   helper — must be promoted to a normative spec when a second
   implementation lands).

## Why this matters

The Python codec defines the canonical-body byte representation
**by implementation**: `json.dumps(body, sort_keys=True,
separators=(",", ":"), default=str)`. A second implementation in a
different language is the load-bearing way to prove the schema is
platform-agnostic — if Rust and Python both compute the same HMAC
over the same JSON-encoded body, the canonical form is genuinely
specified.

Without that second implementation, "the schema is portable" is an
assertion, not a property.

## See also

- [`SCHEMAS.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/SCHEMAS.md) — the wire-format catalogue (currently Python-only)
- [`docs/STABILITY.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/docs/STABILITY.md) — the Python-API stability contract (the runtime counterpart of the wire-format contract)
- [RFC 0002](https://github.com/IdirBenSlama/Ophamin/blob/main/docs/rfc/0002-sota-elevation-stages-5-and-6.md) §3.1 E9 — the elevation roadmap
