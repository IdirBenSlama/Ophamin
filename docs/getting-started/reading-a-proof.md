# Reading a signed Empirical Proof Record

Every Ophamin scenario produces a signed JSON record. This page walks
through what each section means and how to inspect it.

## Quick inspection

```bash
ophamin schema info path/to/proof.json
```

Output:

```
path:           path/to/proof.json
detected kind:  proof
schema_version: 1.0
signature:      f3a8c91b2d7e4f5a6b9c… (present)
```

## Structural validation

```bash
ophamin schema validate path/to/proof.json
```

Validates the JSON against the codec's structural expectations
(JSON Schema). Exit code 0 on success, 2 on any failure.

## Signature verification

```bash
ophamin schema validate path/to/proof.json --key '<your hmac key>'
```

The HMAC key is whatever was passed to `Scenario.run(sign_key=...)`
when the proof was produced. The default key is
`ophamin-default-sign-key` for demos; production uses a per-deployment
key kept in your secret store.

## Anatomy of a proof — the nine sections

### 1. Identity

```json
{
  "proof_id": "a3b9f8c2d4e5f6a7b8c9d0e1f2a3b4c5",
  "schema_version": "1.0",
  "ophamin_version": "0.8.0",
  "ophamin_git_commit": "583e660a...",
  "created_at": "2026-05-17T11:00:00Z"
}
```

`proof_id` is a SHA-256 hash over the canonical body — bit-stable
across machines + Python versions for the same input.

### 2. Claim

The falsifiable statement, captured as a five-tuple:

```json
{
  "statement": "the GWF's false-positive rate on benign payloads is ≤ 10%",
  "operationalization": "blocked / total_benign across the offensive-security corpus",
  "threshold": {"metric": "false_positive_rate", "comparator": "<=", "value": 0.1, "units": "fraction"},
  "h0": "FP rate > 10%",
  "h1": "FP rate ≤ 10%"
}
```

The comparator + value define the **falsification line**: a Verdict of
VALIDATED means the observed value satisfies the comparator; REFUTED
means it doesn't; INCONCLUSIVE means the data was insufficient to
decide either way.

### 3. Pre-registration

The anti-p-hacking lock. Captured BEFORE the run:

```json
{
  "config_hash": "...sha256 over the scenario config...",
  "data_hash": "...sha256 over the corpus...",
  "analysis_plan": "Compute FP rate as ratio; Wilson 95% CI; decide against threshold."
}
```

`config_hash` + `data_hash` together prove the scenario didn't shift
its analysis plan based on what it saw.

### 4. Data

What was actually run against, with provenance:

```json
{
  "substrate_name": "kimera_swm",
  "substrate_git_commit": "abc123...",
  "datasets": [{"name": "cyber", "content_hash": "...", "n_records": 1234, "source": "...", "kind": "..."}]
}
```

### 5. Evidence

Per-pillar statistics with library attribution:

```json
[
  {
    "pillar": "O.spc",
    "statistic_name": "false_positive_rate",
    "statistic_value": 0.087,
    "library": "statsmodels",
    "library_version": "0.14.4",
    "ci_low": 0.072,
    "ci_high": 0.105,
    "cross_check": "n/a"
  }
]
```

The `library` + `library_version` are non-negotiable: every pillar
delegates to a mature library (statsmodels / mapie / river / etc.)
and that attribution rides with the proof for audit purposes.

### 6. Verdict

The decision:

```json
{
  "outcome": "VALIDATED",
  "observed_value": 0.087,
  "threshold": {...same as claim...},
  "reasoning": "observed 0.087 satisfies the pre-registered threshold (<= 0.1)"
}
```

### 7. Reproduction

Exact reproducer:

```json
{
  "command": "python -m ophamin.cli run immune-siege --substrate kimera",
  "environment": {"python": "3.12.7", "ophamin": "0.8.0", "kimera_swm": "abc123"},
  "lineage_chain": ["prev_proof_id_1", "prev_proof_id_2"]
}
```

### 8. Provenance

W3C PROV-JSON graph linking dataset → scenario → substrate → result.
Inspect with any PROV-aware tool (or just JSON.parse).

### 9. Signature

```json
{"signature": "f3a8c91b2d7e4f5a6b9c..."}
```

HMAC-SHA256 over the canonical JSON form of sections 1–8. Bit-stable
across Python 3.10–3.14 and macOS / Linux / Windows.

## What if I want to bulk-validate a directory?

```bash
ophamin schema validate proofs/ --recursive
```

Outputs `OK` / `FAIL` per file plus a summary. Useful for verifying a
whole campaign output, or for forensic re-validation of a historical
proof archive.

## Verifying from outside Python

Ophamin ships **four non-Python paths** for verifying a signed proof.
Every path produces the same `verified=True` for a valid signature
because they all rest on the same canonical-form contract
([`SCHEMAS.md`](../reference/schemas.md) §"Canonical-form determinism
(normative)" R1–R11):

### Rust — for systems integration

```rust
use ophamin_proof::{parse_proof, verify_signature};
use std::fs;

let text = fs::read_to_string("proof.json")?;
let proof = parse_proof(&text)?;
let key = b"ophamin-scenario-proof-key";  // or your deployment key
let ok = verify_signature(&proof, key)?;
assert!(ok);
```

`cargo add ophamin-proof@0.21.2`. Read-side + write-side both
shipped. See
[`crates/ophamin-proof/README.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/crates/ophamin-proof/README.md).

### JavaScript / TypeScript — for web + Node

```typescript
import { readFileSync } from "node:fs";
import { parseProof, verifySignature } from "@ophamin/proof";

const text = readFileSync("proof.json", "utf-8");
const proof = parseProof(text);
const key = new TextEncoder().encode("ophamin-scenario-proof-key");
const ok = await verifySignature(proof, key);
console.log(ok ? "✓ verified" : "✗ FAILED");
```

`npm install @ophamin/proof@0.21.2`. Read-side + write-side both
shipped. See
[`packages/ophamin-proof-js/README.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/packages/ophamin-proof-js/README.md).

### HTTP REST API — for service-style consumers

```bash
ophamin http serve --host 0.0.0.0 --port 8000 &
curl -X POST http://localhost:8000/verify \
    -H "Content-Type: application/json" \
    --data "{\"proof_json\": $(cat proof.json | jq -Rs .)}"
```

Returns `{"verified": true, "verdict": {"outcome": "..."}, "proof_id": "..."}`.
Auto-generated OpenAPI spec at `/openapi.json`; Swagger UI at `/docs`.

### MCP — for AI agents

Wire `ophamin mcp serve` into your MCP client (Claude Code, Cursor,
Cline). The agent gets a `verify_proof` tool with the same return
shape as the HTTP endpoint. See
[`docs/INTEROP_OVERVIEW.md`](../INTEROP_OVERVIEW.md) for client recipes.

### Cross-host: same bytes verify everywhere

The wire-format contract is the load-bearing primitive. A proof
verified by the Rust crate verifies bit-identically under JS, under
the HTTP endpoint, and under MCP — they all canonicalize the same
bytes and compute the same HMAC. Cross-language fixture conformance
tests under [`tests/canonical_form/`](https://github.com/IdirBenSlama/Ophamin/blob/main/tests/canonical_form/)
pin the byte-equality across every release.

## See also

- [`SCHEMAS.md`](../reference/schemas.md) — the versioning policy
- [`docs/SCENARIO_AUTHORING.md`](../SCENARIO_AUTHORING.md) — write your
  own scenarios
- [`docs/INTEROP_OVERVIEW.md`](../INTEROP_OVERVIEW.md) — the full
  5-layer consumer-shape catalogue
- [`docs/REPRODUCING.md`](../REPRODUCING.md) — external-reviewer
  rebuild guide (10-minute reproducer)
