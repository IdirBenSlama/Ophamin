# Ophamin signed-record schemas

> **The framework's load-bearing promise.** Every artefact Ophamin signs
> carries an explicit `schema_version`. This document catalogues every
> versioned schema, the codec that reads/writes it, the
> backward-compat policy, and the migration story.

A signed record (`*.json`) produced under one ophamin version MUST be
readable under every subsequent minor version of ophamin without manual
intervention. Major-version bumps may break that promise, but only with
a published migration script under [`migrations/`](https://github.com/IdirBenSlama/Ophamin/tree/main/migrations) and a
deprecation window of at least one minor release.

This is the **semver promise on the wire** — Python-level API changes are
governed by [`CHANGELOG.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/CHANGELOG.md); this file governs the JSON.

---

## Schema catalogue

### EmpiricalProofRecord — `1.0`

The 9-section signed proof produced by every measurement scenario.

| Field | Value |
|---|---|
| Codec module | [`src/ophamin/measuring/proof/codec.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/src/ophamin/measuring/proof/codec.py) |
| Dataclass | [`src/ophamin/measuring/proof/record.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/src/ophamin/measuring/proof/record.py) `EmpiricalProofRecord` |
| Constant | `SCHEMA_VERSION = "1.0"` |
| Schema doc | [`src/ophamin/measuring/proof/schema.json`](https://github.com/IdirBenSlama/Ophamin/blob/main/src/ophamin/measuring/proof/schema.json) (JSON Schema Draft 2020-12) |
| Validate via | `ophamin schema validate <path.json>` (auto-detects) or `ophamin proof validate <path.json>` |
| Backward-compat read | Reader accepts unknown top-level fields; raises `ProofSchemaVersionMismatchError` on major-version mismatch. Pass `--allow-any-schema-version` to opt out (forensic use only). |
| Stable fields | `proof_id`, `schema_version`, `claim`, `verdict`, `evidence`, `data`, `preregistration`, `reproduction`, `identity`, `signature` |
| Deprecated fields | none |
| Codec round-trip | Property-tested via [`tests/test_proof_record_property.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/tests/test_proof_record_property.py) (Hypothesis, 12 invariants) |

### AuditRecord — `audit/1.1`

The full output of one audit run: per-pillar findings plus optional
pre-registration and verdict (Move L gating).

| Field | Value |
|---|---|
| Codec module | [`src/ophamin/auditing/codec.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/src/ophamin/auditing/codec.py) |
| Dataclass | [`src/ophamin/auditing/audit_record.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/src/ophamin/auditing/audit_record.py) `AuditRecord` |
| Constant | `SCHEMA_VERSION = "audit/1.1"` |
| Validate via | `ophamin schema validate <path.json>` or via the `AuditRecord.from_dict` codec |
| Backward-compat read | **`audit/1.0` reads cleanly under v1.1.** The v1.1 additions (`preregistration`, `chosen_metric`, `verdict`) are optional; their absence on a v1.0 file does not raise. |
| Stable fields | `audit_id`, `schema_version`, `target`, `pillars`, `summary`, `identity`, `signature` |
| Optional in v1.1 | `preregistration`, `chosen_metric`, `verdict` |
| Deprecated fields | none |
| Codec round-trip | Property-tested via [`tests/test_audit_record_property.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/tests/test_audit_record_property.py) (Hypothesis, 16 invariants — surfaced + fixed the `PillarResult.extra` round-trip bug in 0.7.0) |

### CampaignRecord — `2.0` (current)

The 6-phase composite-run aggregate produced by `ophamin run-all`.

| Field | Value |
|---|---|
| Codec module | [`src/ophamin/campaign.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/src/ophamin/campaign.py) (`dump_campaign` / `load_campaign`) |
| Dataclass | `CampaignRecord` (same file) |
| Constants | `CAMPAIGN_SCHEMA_VERSION = "2.0"` (writer); `SUPPORTED_CAMPAIGN_SCHEMA_VERSIONS = {"1.0", "2.0"}` (reader) |
| Validate via | `ophamin schema validate <path.json>` |
| Backward-compat read | **v1.0 records readable + signature-verifiable under v2.0.** The `_body()` canonical form is version-aware — it excludes the v2.0 additive fields when `schema_version == "1.0"`, so legacy signatures still re-verify bit-equal. Unknown `schema_version` values are rejected loud (`ValueError`) per `load_campaign`. |
| Stable fields | `campaign_id`, `schema_version`, `target_name`, `target_git_commit`, `started_at`, `completed_at`, `phases`, `ophamin_version`, `ophamin_git_commit`, `signature` |
| New in v2.0 (RFC 0002 Phase E2) | `corrected_verdicts: dict[str, str]` (claim_id → FWER-corrected verdict), `multiplicity_correction_method: str` (one of `"holm"` / `"bh"` / `"none"`) |
| Phase-shape | Each phase declared in `CANONICAL_PHASE_ORDER`; status ∈ `{"ok", "skipped", "failed"}` |
| Deprecated fields | none |
| Migration | v1.0 → v2.0 is strictly additive; readers handle v1.0 natively. Optional rewrite via [`migrations/campaign_1_to_2.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/migrations/campaign_1_to_2.py). |
| Codec round-trip | Tested in [`tests/test_campaign.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/tests/test_campaign.py) + [`tests/test_campaign_schema_v2.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/tests/test_campaign_schema_v2.py) (11 tests pinning v1↔v2 round-trip + signature) |

### RegressionAlertRecord — `regression-alert/1.0`

The cross-commit drift-detection record emitted by the comparing wheel.

| Field | Value |
|---|---|
| Codec module | [`src/ophamin/comparing/regression_alert.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/src/ophamin/comparing/regression_alert.py) |
| Dataclass | `RegressionAlertRecord` (same file) |
| Constant | `REGRESSION_ALERT_SCHEMA_VERSION = "regression-alert/1.0"` |
| Validate via | `ophamin schema validate <path.json>` |
| Backward-compat read | Reader accepts unknown fields; missing `schema_version` defaults to current. |
| Stable fields | `alert_id`, `schema_version`, `before_proof_id`, `after_proof_id`, `delta`, `verdict_changed`, `signature` |
| Deprecated fields | none |
| Codec round-trip | Tested in [`tests/test_regression_alert.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/tests/test_regression_alert.py) |

### DriftScan — `2`

The streaming-drift-event record produced by the observability pillar
(River ADWIN backend).

| Field | Value |
|---|---|
| Codec module | [`src/ophamin/comparing/drift_detection/river_detector.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/src/ophamin/comparing/drift_detection/river_detector.py) |
| Dataclass | `DriftScan` (same file) |
| Constant | `DRIFT_SCHEMA_VERSION = 2` |
| Validate via | DriftScan codec; CLI exposure pending |
| Backward-compat read | **v1 records readable under v2.** The v2 additions (`pre_registration`, `pre_registered_metric`, `verdict`) are optional. |
| Stable fields | `events`, `metric_name`, `n_observations`, `schema_version` |
| Optional in v2 | `pre_registration`, `pre_registered_metric`, `verdict` |
| Migration | v1→v2: no migration required; v2 readers default missing fields to `None`. |

### Surface inventory schemas — `1`

Three structural-probe artefacts emitted by `seeing/` probes. They are
NOT signed (no `signature` field) — they are descriptive and content-
addressed only.

| Schema | Module | Constant |
|---|---|---|
| KimeraInventory | [`src/ophamin/seeing/discovery/kimera_inventory.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/src/ophamin/seeing/discovery/kimera_inventory.py) | `INVENTORY_SCHEMA_VERSION = 1` |
| TelemetryPrometheusSnapshot | [`src/ophamin/seeing/telemetry/prometheus_probe.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/src/ophamin/seeing/telemetry/prometheus_probe.py) | `TELEMETRY_SCHEMA_VERSION = 1` |
| WiringReport | [`src/ophamin/seeing/wiring/wiring_probe.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/src/ophamin/seeing/wiring/wiring_probe.py) | `WIRING_SCHEMA_VERSION = 1` |

Backward-compat: all three readers accept unknown fields; future major
bumps will follow the same migration pattern as signed records.

---

## Migration policy

### Minor version bumps (1.0 → 1.1 → 1.2 …)

**Forward-additions only.** A minor bump may:
- ADD new top-level fields (must be optional on read)
- ADD new enum values to existing fields (readers tolerate unknown values)
- ADD new sections to nested records
- TIGHTEN validation in the codec (a previously-loose field becomes
  required) **only when the field was already always-emitted by the
  framework's own writers**

A minor bump may NOT:
- remove fields
- rename fields (use a deprecation cycle: add new, mark old, remove in major)
- change a field's type (string → int, etc.)
- change canonical-form serialisation (changing `sort_keys` ordering,
  whitespace, float formatting) — this breaks signature verification

### Major version bumps (1.x → 2.0)

A major bump MAY:
- remove deprecated fields (must have been deprecated ≥ 1 minor version)
- rename fields
- restructure nested records
- add new top-level fields that change verdict semantics (e.g. FWER
  correction in `CampaignRecord/2.0` — purely additive on wire, but
  the meaning of the aggregate verdict changes when `corrected_verdicts`
  is populated)

A major bump MUST ship:
- a migration script under `migrations/` named `<schema>_<from>_to_<to>.py`
- documentation in the CHANGELOG entry under "Schema migrations"
- backward-compat-on-read: the new reader MUST handle records emitted
  at every prior version still in `SUPPORTED_*_SCHEMA_VERSIONS`

#### Case study — `CampaignRecord/1.0 → 2.0` (RFC 0002, Phase E2)

The first major bump of a signed-record schema in Ophamin's history.
Reference implementation pattern for future additive bumps:

1. Add two strictly-additive fields to the dataclass with defaults.
2. Make `_body()` **version-aware**: include the new fields iff
   `schema_version != "1.0"`. This is the load-bearing trick that keeps
   1.0 signatures verifiable under a 2.0-aware reader.
3. Update `from_dict` to default the new fields when absent (so 1.0
   wire records load cleanly without manual migration).
4. Add `SUPPORTED_*_SCHEMA_VERSIONS = frozenset({"1.0", "2.0"})` and
   loud-reject unknown versions in `from_dict`.
5. Ship the migration script ([`migrations/campaign_1_to_2.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/migrations/campaign_1_to_2.py)) — optional
   from the user's perspective (readers handle 1.0 natively), but
   provided for operators who want to rewrite their historical corpus
   into the 2.0 wire form.

Tests pin every invariant: see
[`tests/test_campaign_schema_v2.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/tests/test_campaign_schema_v2.py).

### Deprecation cycle

Removing a field requires:

1. Add a `## Deprecated fields` row to this catalogue (current version)
2. Codec continues to read it for at least 1 minor version
3. Major bump removes the field; migration script drops it
4. CHANGELOG explicitly calls out the removal

---

## Canonical-form determinism (normative)

Every signed record's `signature` is HMAC-SHA256 over the **canonical
byte representation** of the record's body (the body is the record's
dict minus the `signature` field, in the layout the dataclass's
`_body()` returns). This section is **normative** — it specifies the
exact byte sequence a cross-language implementation MUST produce to
verify a Python-emitted Ophamin record byte-for-byte. RFC 0002 Phase
E9 requires this to be normative because cross-language read APIs
(Rust `ophamin-proof`, JS/TS package) cannot reuse Python's
`json.dumps`; they must reproduce its output exactly.

### Reference implementation

The Python reference is one line:

```python
json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
```

with all other `json.dumps` parameters at Python stdlib defaults
(notably `ensure_ascii=True` and `allow_nan=True`).

### Rule-by-rule normative spec

A conformant canonical-form encoder MUST produce the exact byte
sequence Python's `json.dumps(..., sort_keys=True, separators=(",", ":"))`
produces for any JSON-native input. The rules below enumerate every
behavior the byte sequence depends on.

**R1 — encoding.** Output is UTF-8 bytes. Because of R6, every output
byte is in fact 7-bit ASCII (`0x20`–`0x7E` plus `\n` `\t` `\b` `\f` `\r`
inside string-escape sequences — see R6); UTF-8 is the declared
encoding rather than ASCII to keep the door open for a future
`ensure_ascii=False` mode (would be a major schema bump).

**R2 — separators.** No whitespace between tokens. The exact two
separators are: `,` (between elements of an array and between key-value
pairs of an object) and `:` (between a key and its value in an
object). No space after `:`, no space before `,`, no newlines, no
trailing comma, no leading/trailing whitespace at the document level.

**R3 — object key ordering.** Object keys MUST be emitted in
ascending order by Python's default string `<` operator, which is
**Unicode code-point order**. This is recursive: every nested object
is also key-sorted. Concrete example: the keys `{"10", "2", "A", "b"}`
sort as `"10" < "2" < "A" < "b"` (codepoint 49 < 50 < 65 < 98) and the
emitted object is `{"10":3,"2":4,"A":2,"b":1}`.

**R4 — integers.** A value of Python type `int` MUST be emitted as a
plain integer literal: optional leading minus sign, no decimal point,
no exponent, no leading zeros, decimal digits only. Examples:
`0`, `-1`, `1000000`. No `+` prefix on positive values.

**R5 — floats.** A value of Python type `float` MUST be emitted as
Python's `repr(float)` produces it — the shortest decimal string that
round-trips to the same `float` value under IEEE-754 double. Five
subcases an implementer must reproduce:

| Input | Output |
|---|---|
| `0.0` | `0.0` (trailing `.0` ALWAYS present — distinguishes float from int) |
| `-0.0` | `-0.0` (negative zero preserved) |
| `3.14159` | `3.14159` |
| `1e20` | `1e+20` (note: explicit `+` sign in exponent) |
| `1e-7` | `1e-07` (note: 2-digit zero-padded exponent for negative exponents) |

The exponent format is Python's `repr`: positive exponents carry an
explicit `+`; the exponent itself has at least 2 digits when negative
(`1e-07`) but is not zero-padded when positive (`1e+20`). Cross-language
implementers should test against Python `repr` directly.

**R6 — strings.** A value of Python type `str` MUST be emitted as a
JSON string literal under `ensure_ascii=True` semantics:

- Wrapped in `"` (double-quote).
- The following characters are escaped: `"` → `\"`, `\` → `\\`,
  `\b` (BS, U+0008) → `\b`, `\f` (FF, U+000C) → `\f`, `\n` → `\n`,
  `\r` → `\r`, `\t` → `\t`.
- All other control characters in U+0000 through U+001F are escaped
  as a 6-byte sequence `\uXXXX` where `XXXX` is the lowercase hex
  code point, e.g. U+0000 -> `\u0000`, U+001F -> `\u001f`.
- Every character with code point U+0080 or above is escaped as
  `\uXXXX` (lowercase hex). For code points above U+FFFF, Python
  emits a UTF-16 surrogate pair: `😀` (etc.).
- Code points U+0020–U+007E (printable ASCII) except `"` and `\` are
  emitted verbatim.

Concrete: `"café"` becomes `"café"`. `"a\nb"` becomes `"a\nb"`
(escape sequence `\n` is two characters: backslash and `n`).

**R7 — booleans and null.** `True` → `true`, `False` → `false`,
`None` → `null` (lowercase, no quoting).

**R8 — arrays.** A Python `list` or `tuple` MUST emit as
`[item1,item2,...]` with no whitespace. Tuples become arrays with no
trace of their tuple-vs-list provenance — round-tripping a tuple
through canonical form returns a list. Element order is preserved (no
re-sorting; arrays are ordered).

**R9 — objects.** A Python `dict` MUST emit as
`{"key1":value1,"key2":value2,...}` with keys sorted per R3.
Keys MUST be strings; integer or other-typed keys are NOT supported
in the canonical form. (Python's `json.dumps` will coerce some
non-string keys via `default=`, but conformant Ophamin scenarios
should not produce such records.)

**R10 — NaN and Infinity.** The reference encoder runs with
`allow_nan=True` (default), which emits bare `NaN`, `Infinity`, and
`-Infinity` literals. **These are non-standard JSON** — strict JSON
parsers (including some Rust and JS libraries) reject them. The
schema-level commitment for Ophamin records:

- The encoder accepts NaN/Inf as input and emits the bare literals.
- A conformant cross-language decoder MUST accept the bare literals
  in order to verify Python-emitted signatures.
- Scenario authors SHOULD NOT emit NaN or Infinity in proof bodies
  (use a `string` representation like `"NaN"` if needed); records
  containing them are non-portable to strict-JSON consumers.
- Records produced by core Ophamin scenarios are scanned by the audit
  pillars and are known to contain no bare NaN/Inf.

**R11 — non-JSON-native types.** The `default=str` fallback converts
any non-JSON-native value (datetime, Decimal, custom dataclass…) to
its Python `str(obj)` representation. **This output is NOT portable**
— a Rust implementation cannot reproduce Python's
`str(datetime(2026,5,18,tzinfo=UTC))` byte-for-byte. Scenario authors
SHOULD ensure every value in the proof body is one of the JSON-native
types (`str`, `int`, `float`, `bool`, `None`, `list`, `tuple`, `dict`)
before signing. The `default=str` is a development safety net, not a
portable feature.

### Body field layout

The `_body()` of an `EmpiricalProofRecord` is the dict the signature
covers. After R3 (key-sort), the top-level keys appear in this exact
order in the canonical byte stream:

```
claim, data, evidence, identity, preregistration, provenance, reproduction, schema_version, verdict
```

Each value is recursively canonicalized per R1–R11. The `signature`
field is computed AFTER canonicalization (it is the HMAC over the
body's canonical bytes) and is then set on the record; it is NOT
itself part of the body.

For the other signed schemas (`CampaignRecord`, `AuditRecord`,
`RegressionAlertRecord`, …) the body layout is documented in each
schema's codec module and follows the same recursive
canonicalization rules.

### Stability guarantees

The signature is **bit-stable** across these axes:

- Python 3.10 – 3.14 (verified by CI test matrix)
- macOS / Linux / Windows
- `json` stdlib vs `orjson` (both reproduce the rule set above)
- `cpython` vs `pypy` (so long as the float `repr` shortest-round-trip
  algorithm is consistent)

The signature is **NOT stable** if any of these are changed:

- `sort_keys=True` flipped off → R3 violated, key order is dict-insertion-order
- separators changed → R2 violated, byte sequence drifts
- `ensure_ascii=False` → R6 violated, non-ASCII emitted as UTF-8 bytes
  rather than `\uXXXX` escapes
- `allow_nan=False` → R10 violated, NaN/Inf raises instead of emitting

Any future canonical-form change is a **MAJOR Ophamin version bump**
with a migration script under [`migrations/`](https://github.com/IdirBenSlama/Ophamin/tree/main/migrations) that re-signs every
existing proof under the new rules. The current rule set is pinned to
**schema_version `1.0`** for `EmpiricalProofRecord` and the
equivalent versions for the other schemas.

### Cross-language test fixtures

Three reference records and their expected canonical byte
representations are checked into [`tests/canonical_form/`](https://github.com/IdirBenSlama/Ophamin/tree/main/tests/canonical_form).
Each fixture is:

- `<name>.input.json` — the Python dict to canonicalize (already
  JSON-serialized so it is language-neutral)
- `<name>.canonical.bytes` — the expected canonical byte string
- `<name>.hmac_sha256.hex` — the expected HMAC-SHA256 hex digest
  under the test key `b"ophamin-canonical-test-key-v1"`

Any cross-language implementation (Rust `ophamin-proof`, JS/TS
codec, future bindings) MUST produce byte-equivalent output on all
three fixtures to claim conformance. The Python reference is also
re-tested against these fixtures on every CI run
([`tests/test_canonical_form_fixtures.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/tests/test_canonical_form_fixtures.py)) — any drift in the
Python emitter would fail CI loud before it shipped.

---

## Validating a record

```bash
# Auto-detect schema, validate structure + signature
ophamin schema validate path/to/record.json

# Inspect what schema was detected (no validation)
ophamin schema info path/to/record.json

# Validate a directory of records
ophamin schema validate path/to/proofs/ --recursive

# Allow major-version mismatch (forensic use only)
ophamin schema validate path/to/record.json --allow-any-schema-version
```

See [`src/ophamin/cli.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/src/ophamin/cli.py) `cmd_schema` for the
implementation. The dispatch table maps every documented
`schema_version` value to its codec module's validator.
