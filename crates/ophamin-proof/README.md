# `ophamin-proof`

> Read-only verifier for Ophamin signed empirical-proof records.
> Byte-equivalent to the Python reference canonical form per
> [`SCHEMAS.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/SCHEMAS.md)
> §"Canonical-form determinism (normative)".

This is the **Rust half** of Ophamin's cross-language interop
contract (RFC 0002 Phase E9). It provides:

- **Read side** (since 0.16.0): parse a signed `EmpiricalProofRecord`
  from the wire form, reconstruct the canonical body bytes Python
  signed over, and verify the HMAC-SHA256 signature.
- **Write side** (since 0.21.0): produce canonical bytes + signed
  HMAC from native Rust primitives. A `CanonicalValue` enum (with
  distinct `Int`/`Float` variants so the Python int/float
  distinction is type-enforced) is the input; `canonicalize_bytes`
  + `sign_canonical` are the entry points.

The round-trip is symmetric: a Rust-produced canonical-byte stream
verifies under Python (and JS) byte-for-byte. The cross-language
fixtures (`tests/canonical_form/*`) lock in both directions.

## Cargo manifest

```toml
[dependencies]
ophamin-proof = "0.16"
```

Rust ≥ 1.75 (no `nightly` features).

## Quick start

```rust
use ophamin_proof::{parse_proof, verify_signature};

let text = std::fs::read_to_string("path/to/some-proof.json")?;
let proof = parse_proof(&text)?;
// The deployment's signing key. For the default Ophamin scenarios,
// this is the same bytes Python's
// ophamin.measuring.scenarios.base.DEFAULT_SIGN_KEY uses.
let key = b"ophamin-scenario-proof-key";
assert!(verify_signature(&proof, key)?);
# Ok::<(), Box<dyn std::error::Error>>(())
```

## Runnable examples

Two `cargo run --example` demos under [`examples/`](examples/):

```bash
# Read side: verify any shipped proof
cargo run --example verify_proof
# Or with an explicit path:
cargo run --example verify_proof -- path/to/proof.json

# Write side: build a CanonicalValue tree in Rust, canonicalize,
# and sign with HMAC-SHA256
cargo run --example sign_value
```

Each example is heavily annotated and exits non-zero on any
contract drift — they double as smoke tests for the consumer-facing
surface.

## What's in the crate

**Read side** (parse + verify Python-emitted records):

| Surface | Purpose |
|---|---|
| `parse_proof(text: &str) -> Result<EmpiricalProofRecord, ProofError>` | Parse a wire-form JSON record. |
| `EmpiricalProofRecord` | Read-only view of the 9-section record. Fields use `serde_json::Value` so callers can re-deserialize specific fields into their own types via `serde_json::from_value` as needed. |
| `canonical_body_bytes(&record) -> Result<Vec<u8>>` | Reconstruct the body bytes Python signed over. Use this for ad-hoc verification of an arbitrary HMAC key or hash construction. |
| `verify_signature(&record, key) -> Result<bool>` | HMAC-SHA256 verify. Constant-time compare via `subtle`. |
| `compute_proof_id(&record) -> Result<String>` | SHA-256 of the canonical body bytes (content-addressed identifier). |
| `testing::canonicalize_value_to_bytes(value)` | Encode any `serde_json::Value` to canonical UTF-8 bytes. Not part of the stable API — exposed for cross-language conformance tests. |

**Write side** (build native values + emit canonical bytes + sign):

| Surface | Purpose |
|---|---|
| `CanonicalValue` (in `writer` module) | Value enum with distinct `Int(i64)` / `Float(f64)` variants so Python's int/float distinction is type-enforced from construction. |
| `canonicalize_bytes(&value) -> Result<Vec<u8>>` | Produce the canonical UTF-8 bytes per SCHEMAS.md R1–R11. |
| `sign_canonical(&value, key) -> Result<String>` | HMAC-SHA256 hex digest a Python verifier accepts. |
| `python_repr(f64) -> Result<String>` | Standalone float formatter byte-equivalent to Python's `repr(float)`. Useful when implementing custom encoders. |

## Cross-language conformance

The crate is tested against three reference fixtures committed in
the main Ophamin repo at
[`tests/canonical_form/`](https://github.com/IdirBenSlama/Ophamin/tree/main/tests/canonical_form):

| Fixture | What it covers |
|---|---|
| `simple` | Basic types, recursive key sort, lowercase null/true/false. |
| `unicode` | Non-ASCII strings (Latin supplement / Cyrillic / CJK), non-ASCII keys, supplementary-plane emoji (UTF-16 surrogate pair). |
| `numerical_edge` | Float formatting edge cases: `1e+20`, `1e-07`, `-0.0`, `0.0` vs integer `0`. |

Each fixture has three artefacts (`<stem>.input.json`,
`<stem>.canonical.bytes`, `<stem>.hmac_sha256.hex`); the integration
test suite at [`tests/fixture_conformance.rs`](tests/fixture_conformance.rs)
asserts byte-equivalence on all three plus signature verification
on every shipped Python-emitted proof under
[`proofs/measurement_machinery/`](https://github.com/IdirBenSlama/Ophamin/tree/main/proofs/measurement_machinery).

The same fixtures back the
[`@ophamin/proof`](../../packages/ophamin-proof-js) JS/TS port, so
the contract runs three ways: Python emits, Rust verifies, JS
verifies. All three produce identical canonical bytes on the same
input, and identical HMAC digests under the same key.

A drift in any side fails CI loud.

## Design notes

### Int-vs-float distinction preserved at parse time

`serde_json` is enabled with the `arbitrary_precision` feature, which
keeps every parsed number as its original lexical string. Python
emits ints without a decimal point (`30`) and floats with one
(`30.0`); the lexical preservation passes that distinction through
unchanged into our canonical-form output.

This is load-bearing: a Python `int 30` and a Python `float 30.0`
produce different canonical bytes, so different HMAC digests. The
default serde_json behavior (without `arbitrary_precision`) would
silently collapse them.

### Float formatting deferred to Python's lexical form

For Python-emitted records, the float lexical forms (`1e+20`,
`1e-07`, `-0.0`) are already in canonical form. The Rust port
preserves them through `serde_json`'s lexical preservation rather
than reimplementing Python's `repr(float)` byte-for-byte.

A consequence: this crate is a **read-only verifier**, not a
canonical-form **writer**. Producing canonical bytes from
arbitrary `f64` values in Rust would require reimplementing
Python's `repr` (with its specific thresholds at 1e-4 / 1e16 and
its `e+NN` / `e-NN` exponent padding). That is left as future work
when E9 expands to a write-side counterpart.

### String escaping is reimplemented

`serde_json`'s default `ensure_ascii` behavior emits non-ASCII
characters as UTF-8 bytes, not as `\uXXXX` escapes. The Python
reference uses `ensure_ascii=True`, so the crate reimplements
string escaping per `SCHEMAS.md` R6 (lowercase hex, UTF-16
surrogate pairs for supplementary plane).

### Constant-time signature compare

Signatures are compared via `subtle::ConstantTimeEq` on the hex
strings rather than naïve `==`. Prevents a timing side-channel on
adversarial signature payloads.

## Build + test (for contributors)

```bash
cd crates/ophamin-proof
cargo test                                # all unit + integration tests
cargo test fixture_canonical_bytes        # just the fixture pin
cargo test shipped_proofs                 # just the Python-emitted-proof verify
```

The integration tests resolve paths relative to `CARGO_MANIFEST_DIR`,
expecting the crate to live two levels deep from the repo root
(`<repo>/crates/ophamin-proof/`). Run from anywhere; cargo handles
the path.

## Versioning

The crate's version tracks the main Ophamin release that shipped
its current implementation (currently `0.16.0`). The wire-format
contract is governed by `SCHEMAS.md` and is **separately** versioned
(currently `1.0` for `EmpiricalProofRecord`); the Rust crate's
major version bumps if and only if the wire format's major version
bumps.

## See also

- [`SCHEMAS.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/SCHEMAS.md) — normative byte-form specification (R1–R11).
- [`tests/canonical_form/`](https://github.com/IdirBenSlama/Ophamin/tree/main/tests/canonical_form) — cross-language test fixtures.
- [`packages/ophamin-proof-js`](../../packages/ophamin-proof-js) — the parallel JS/TS port.
- [RFC 0002 §3.1 E9](https://github.com/IdirBenSlama/Ophamin/blob/main/docs/rfc/0002-sota-elevation-stages-5-and-6.md) — the elevation phase that names cross-language interop as a state-of-the-art-tier requirement.
