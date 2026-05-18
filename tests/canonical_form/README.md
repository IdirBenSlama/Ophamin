# Canonical-form cross-language test fixtures

These fixtures pin the **canonical byte representation** an Ophamin
signed record's body MUST produce, per the normative rules in
[`SCHEMAS.md`](../../SCHEMAS.md) §"Canonical-form determinism".

They exist so that a non-Python implementation of the canonical-form
encoder (Rust `ophamin-proof`, JS/TS `@ophamin/proof`, future
bindings) can be tested for byte-equivalence against the Python
reference without needing a Python runtime.

## Fixture layout

Each fixture is three files with a shared stem `<name>`:

| File | Format | Purpose |
|---|---|---|
| `<name>.input.json` | JSON | Language-neutral input. Parse it into your language's native dict / map / object. |
| `<name>.canonical.bytes` | raw bytes (UTF-8) | What the canonical encoder must produce on the parsed input. Compare byte-for-byte. |
| `<name>.hmac_sha256.hex` | ASCII hex, single line, trailing newline | HMAC-SHA256 of the canonical bytes under the test key, lowercase hex. |

The test key is the same for every fixture:

```
b"ophamin-canonical-test-key-v1"
```

(29 bytes, ASCII; the exact byte sequence
`6f 70 68 61 6d 69 6e 2d 63 61 6e 6f 6e 69 63 61 6c 2d 74 65 73 74 2d 6b 65 79 2d 76 31`).

The HMAC is the same primitive Ophamin uses for production signatures
(`hmac.new(key, canonical_bytes, hashlib.sha256).hexdigest()`); a
cross-language port that matches both `canonical.bytes` and
`hmac_sha256.hex` is signature-compatible with the Python emitter.

## Current fixtures

| Stem | What it exercises |
|---|---|
| `simple` | Basic types (str, int, float, bool, None, list, dict) and the load-bearing key-sort. |
| `unicode` | Non-ASCII strings (Latin-1 supplement, Cyrillic, CJK), an emoji exercising the UTF-16 surrogate pair rule, and a non-ASCII object key. |
| `numerical_edge` | Numerical edge cases: `0.0` vs `0`, `-0.0` preserved, `1e+20` and `1e-07` exponent formats, very small and very large floats. |

## How to verify (Python reference)

```bash
pytest tests/test_canonical_form_fixtures.py -v
```

The test loads each fixture, applies the reference canonical encoder,
and asserts both byte-equivalence and HMAC equivalence. Any drift in
the Python emitter fails CI loud before shipping.

## How to verify (cross-language port)

A conformant port MUST pass for all three fixtures:

```text
canonicalize(parse_json(<name>.input.json)) == read_bytes(<name>.canonical.bytes)
hmac_sha256(test_key, read_bytes(<name>.canonical.bytes)).hex() == read_text(<name>.hmac_sha256.hex).strip()
```

If any fixture fails, the port has drifted from the spec and signed
records produced under it WILL NOT cross-verify with Python-emitted
records.

## Adding a new fixture

1. Add the input to `tests/canonical_form/_generate_fixtures.py` under a
   new stem.
2. Re-run `python -m tests.canonical_form._generate_fixtures` to write
   the three artefacts.
3. Add the stem to `_FIXTURE_STEMS` in
   `tests/test_canonical_form_fixtures.py`.
4. Commit all three artefacts plus the generator + test update in one
   change. The fixtures are content-addressed by their inputs; never
   hand-edit `<name>.canonical.bytes` or `<name>.hmac_sha256.hex`.

## NaN, Infinity, and `default=str` are intentionally absent

The spec marks bare `NaN`, `Infinity`, `-Infinity`, and the
`default=str` fallback as non-portable. Records that contain them
remain Python-verifiable but cross-language ports are not required to
reproduce them. The fixtures here therefore stay inside the portable
subset.
