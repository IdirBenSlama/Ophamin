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

## Canonical-form determinism

Every signed record's `signature` is HMAC-SHA256 over the canonical JSON
form of the record's body (sans `signature`). Canonical form is:

- `json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)`
- Integers stay int; floats stay float (Move L coercion ensures
  `Threshold(value=10)` becomes `10.0` in the body, never `10`)
- `None` stays as JSON `null`
- Strings are UTF-8
- Tuples become JSON arrays (no other tuple-vs-list distinction
  survives the wire)

**The signature is bit-stable across:**
- Python 3.10–3.14
- macOS / Linux / Windows
- `json` stdlib vs `orjson`

**The signature is NOT stable across:**
- changing `sort_keys` ordering or separators
- migrating to a different hash function

If a future ophamin version needs to change canonical form, that is a
**major version bump** with a forced re-signature step in the migration
script — old signatures will not verify against the new canonical form.

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
