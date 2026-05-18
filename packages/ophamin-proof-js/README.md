# `@ophamin/proof`

> Read-only verifier for Ophamin signed empirical-proof records.
> Byte-equivalent to the Python reference canonical form per
> [`SCHEMAS.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/SCHEMAS.md)
> §"Canonical-form determinism (normative)".

This is the **JavaScript/TypeScript half** of Ophamin's
cross-language interop contract (RFC 0002 Phase E9). It provides:

- **Read side** (since 0.16.0): parse a signed `EmpiricalProofRecord`
  from the wire form, reconstruct the canonical body bytes Python
  signed over, and verify the HMAC-SHA256 signature.
- **Write side** (since 0.21.0): produce canonical bytes + signed
  HMAC from native JS values. `canonicalize` + `signCanonical` are
  the entry points; use the exported `PyInt` class to mark integers
  explicitly where Python would emit an int (no trailing `.0`).

The round-trip is symmetric: a JS-produced canonical-byte stream
verifies under Python (and Rust) byte-for-byte. The cross-language
fixtures (`tests/canonical_form/*`) lock in both directions.

## Installation

```bash
npm install @ophamin/proof
```

Node ≥ 18 (uses `node:crypto`, `import.meta.dirname`, and stdlib JSON
parse). No runtime dependencies.

## Quick start

```typescript
import { readFileSync } from "node:fs";
import { parseProof, verifySignature } from "@ophamin/proof";

const text = readFileSync("path/to/some-proof.json", "utf-8");
const proof = parseProof(text);

// The deployment's signing key. For the default Ophamin scenarios,
// this is the same bytes Python's
// ophamin.measuring.scenarios.base.DEFAULT_SIGN_KEY uses.
const key = new TextEncoder().encode("ophamin-scenario-proof-key");

if (verifySignature(proof, key)) {
  console.log(`✓ verified ${proof.verdict.outcome} on ${proof.claim.statement}`);
} else {
  console.error("✗ signature mismatch — record has been tampered with");
}
```

## What's in the package

| Module | Purpose |
|---|---|
| `@ophamin/proof` | Main entry. Re-exports `parseProof`, `verifySignature`, `canonicalize`, `pythonRepr`, `escapeString`, `parseJsonPreservingInts`, and the type definitions. |
| `@ophamin/proof/canonical` | The canonical-form encoder (`canonicalize`, `canonicalBytes`, `pythonRepr`, `escapeString`, `PyInt`). Use directly when you need to produce canonical bytes for any JSON-native value. |
| `@ophamin/proof/proof` | The record parser + signature verifier. Use this when working with `EmpiricalProofRecord` artefacts. |

## Why the canonical-form encoder exists

JS's `JSON.stringify` is NOT byte-equivalent to Python's
`json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)`
on multiple axes:

| Axis | `JSON.stringify` | Python `json.dumps` (Ophamin canonical) | Our encoder |
|---|---|---|---|
| Object key order | insertion order | sorted (Unicode code-point, recursive) | sorted to match Python |
| Float `1e20` | `100000000000000000000` (fixed-point up to 1e21) | `1e+20` (scientific at ≥ 1e16) | `1e+20` |
| Float `1e-7` | `1e-7` (1-digit exponent) | `1e-07` (2-digit zero-padded) | `1e-07` |
| Non-ASCII string | raw UTF-8 (`"café"`) | `\uXXXX` escapes (`"café"`) | `\uXXXX` escapes |
| Integer `30` | `30` | `30` | `30` (via `PyInt`) |
| Float `30.0` | `30` (no distinction) | `30.0` | `30.0` (via `PyInt`-vs-number distinction) |

The mismatch on **integer vs float** is load-bearing: a Python
`int 30` and a Python `float 30.0` produce different canonical bytes
(`30` vs `30.0`), so they produce different HMAC signatures. JS's
default `JSON.parse` collapses both to the same JavaScript number,
losing the distinction.

This package's `parseJsonPreservingInts` parser walks the source
text directly and wraps integer literals (no decimal point, no
exponent) in a `PyInt` class. The encoder then formats `PyInt`
without a trailing `.0`, matching Python.

## Cross-language conformance

The package is tested against three reference fixtures committed in
the main Ophamin repo at
[`tests/canonical_form/`](https://github.com/IdirBenSlama/Ophamin/tree/main/tests/canonical_form):

| Fixture | What it covers |
|---|---|
| `simple` | Basic types (str, int, float, bool, null, list, dict) and recursive key sort. |
| `unicode` | Non-ASCII strings, non-ASCII keys, supplementary-plane emoji (UTF-16 surrogate pair). |
| `numerical_edge` | Float-formatting edge cases: `1e+20`, `1e-07`, `-0.0`, `0.0` vs `0`. |

Each fixture has three artefacts (`<stem>.input.json`,
`<stem>.canonical.bytes`, `<stem>.hmac_sha256.hex`); the test suite
asserts byte-equivalence on all three.

The same fixtures are the Python reference's tests, so the contract
runs both ways: Python and JS produce identical canonical bytes on
the same input, and identical HMAC digests under the same key.

A drift in either side fails CI loud.

## What's not supported

Per the spec, the following are **non-portable** and the encoder
will throw on them:

- `NaN`, `Infinity`, `-Infinity` (bare literals in Python `json.dumps`
  output, but non-standard JSON and rejected by strict parsers).
- Python's `default=str` fallback (any Python value that's not
  JSON-native gets `str(obj)`'d at emit time; reproducing `str(datetime)`
  byte-for-byte across languages is not feasible).
- BigInt values (Python's `int` is unbounded; the JS port supports
  only safe integers, i.e. `|x| < 2^53`).

Scenarios that emit any of the above produce records that verify
under the Python reference but not under any non-Python port. Avoid
in scenarios you intend to be interoperable.

## Build + test (for contributors)

```bash
cd packages/ophamin-proof-js
npm install
npm test          # builds + runs node:test with all fixture pins
npm run build     # type-check + emit dist/
```

The test suite runs against the conformance fixtures in the main
repo (path resolved relative to `import.meta.dirname`). Run from
the package directory.

## Versioning

The package's version tracks the main Ophamin release that shipped
its current implementation (currently `0.16.0`). The wire-format
contract is governed by `SCHEMAS.md` and is **separately** versioned
(currently `1.0` for `EmpiricalProofRecord`); the JS package's major
version bumps if and only if the wire format's major version bumps.

## See also

- [`SCHEMAS.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/SCHEMAS.md) — normative byte-form specification (R1–R11).
- [`tests/canonical_form/`](https://github.com/IdirBenSlama/Ophamin/tree/main/tests/canonical_form) — cross-language test fixtures.
- [`crates/ophamin-proof`](https://github.com/IdirBenSlama/Ophamin/tree/main/crates) — the parallel Rust port.
- [RFC 0002 §3.1 E9](https://github.com/IdirBenSlama/Ophamin/blob/main/docs/rfc/0002-sota-elevation-stages-5-and-6.md) — the elevation phase that names cross-language interop as a state-of-the-art-tier requirement.
