# Ophamin interop overview

> One page covering every way to drive, consume, or observe
> Ophamin from outside Python. Eight interop layers stacked so a
> consumer picks the one that fits their shape.

## At a glance

| Consumer shape | Layer | Surface | Read-only? | First shipped |
|---|---|---|---|---|
| Non-Python *systems* needing cryptographic verification | Wire-format ports | `crates/ophamin-proof` (Rust) + `packages/ophamin-proof-js` (JS/TS) — both read AND write | no (write-side since 0.21.0) | `0.16.0` (read), `0.21.0` (write) |
| AI agents speaking MCP | MCP server | `ophamin mcp serve` (stdio / SSE / streamable-http) | one tool writes (`run_scenario`); rest are read | `0.17.0` |
| HTTP / service-style consumers | HTTP REST API | `ophamin http serve` (FastAPI; OpenAPI 3 at `/openapi.json`) | same as MCP | `0.18.0` |
| Event-stream routing infrastructure | CloudEvents 1.0 envelope | `ophamin.cloudevents.wrap` / `unwrap` (Python) | no — wrap is opt-in; routing is read | `0.19.0` |
| Observability backends (Jaeger / Datadog / etc.) | OpenTelemetry instrumentation | `ophamin.observability.setup_otel()` + ambient OTel SDK | n/a (telemetry is one-way) | `0.20.0` |
| Supply-chain attestation (Sigstore / SLSA / Rekor / cosign) | in-toto Attestation Framework v1 (ITE-6) + DSSE envelope | `ophamin.interop.to_in_toto_statement` / `to_dsse_envelope` (Python) | n/a (export only) | `0.35.0` |
| FAIR research-data infrastructure (Zenodo / Galaxy / WorkflowHub) | RO-Crate 1.2 (Research Object Crate, JSON-LD + schema.org) | `ophamin.interop.to_ro_crate_metadata` (Python) | n/a (export only) | `0.36.0` |
| Data-pipeline lineage backends (Airflow / dbt / Spark / Marquez) | OpenLineage 2.0 RunEvent | `ophamin.interop.to_openlineage_event` (Python) | n/a (export only) | `0.37.0` |

All eight layers wrap the **same shared implementations**
(`src/ophamin/interfaces/_impls.py`), so behavioural drift between
them is structurally impossible.

## Choosing your layer

### "I have a record I want to verify, from a non-Python language."

Use the wire-format port for your language:

- **Rust**: `cargo add ophamin-proof@0.21.2` →
  `ophamin_proof::parse_proof(text)` + `ophamin_proof::verify_signature(&record, key)`.
  See [`crates/ophamin-proof/README.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/crates/ophamin-proof/README.md).
- **JS/TS**: `npm install @ophamin/proof@0.21.2` →
  `parseProof(text)` + `verifySignature(record, key)`. See
  [`packages/ophamin-proof-js/README.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/packages/ophamin-proof-js/README.md).

Conformance against the cross-language fixtures is locked: a
record verifying under any port verifies under every port.

### "I want to PRODUCE a record from a non-Python language."

Same packages, write-side surface:

- **Rust**:
  ```rust
  use ophamin_proof::{CanonicalValue, canonicalize_bytes, sign_canonical};
  let mut obj = CanonicalValue::object();
  obj.insert("metric", CanonicalValue::Float(3.14159));
  obj.insert("threshold", CanonicalValue::Float(0.05));
  let sig = sign_canonical(&obj, b"my-deployment-key")?;
  ```
- **JS/TS**:
  ```typescript
  import { PyInt, signCanonical } from "@ophamin/proof";
  const value = { n: new PyInt(30), p: 3.14159 };
  const key = new TextEncoder().encode("my-deployment-key");
  const sig = await signCanonical(value, key);
  ```

The Rust `CanonicalValue` enum and the JS `PyInt` wrapper both
preserve Python's int / float distinction (load-bearing for
byte-equivalent signatures).

### "I'm building an AI agent and want it to drive Ophamin."

Use the MCP server. Install with the `[mcp]` extra:

```bash
pip install 'ophamin[mcp]'
ophamin mcp serve
```

Wire it into your MCP client. For Claude Code:

```jsonc
// ~/.claude/config.json (or equivalent)
{
  "mcpServers": {
    "ophamin": { "command": "ophamin", "args": ["mcp", "serve"] }
  }
}
```

Six tools become available to the agent: `list_scenarios`,
`get_scenario_claim`, `verify_proof`, `canonicalize_value`,
`read_proof_index`, `run_scenario`. See
[`src/ophamin/mcp/README.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/src/ophamin/mcp/README.md) for
client recipes (Claude Desktop, Cursor, Cline, generic stdio
clients).

### "I'm building a service that talks JSON over HTTP."

Use the HTTP REST API:

```bash
ophamin http serve --host 0.0.0.0 --port 8000 --workers 4
```

The eight endpoints mirror the MCP surface plus `/health` and
`/version`. OpenAPI 3 spec at `/openapi.json`; Swagger UI at
`/docs`. See [`src/ophamin/http_api/README.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/src/ophamin/http_api/README.md)
for curl examples + Docker / Kubernetes / systemd deployment
recipes.

### "I want Ophamin records flowing through Kafka / EventBridge / Knative."

Wrap them at production:

```python
from ophamin.cloudevents import wrap
import json

envelope = wrap(proof, source="urn:my-deployment:ophamin")
producer.send(topic="ophamin.proofs", value=json.dumps(envelope).encode())
```

Unwrap at consumption:

```python
from ophamin.cloudevents import unwrap
from ophamin.interfaces._impls import verify_proof_impl

proof = unwrap(envelope_text)
result = verify_proof_impl(json.dumps(proof))
assert result["verified"]
```

See [`src/ophamin/cloudevents/README.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/src/ophamin/cloudevents/README.md)
for the full attribute catalogue + Kafka / EventBridge recipes.

### "I want Ophamin spans in Jaeger / metrics in Prometheus."

Wire OpenTelemetry once at app startup:

```python
from ophamin.observability import setup_otel
setup_otel(otlp_endpoint="http://otel-collector:4318")
```

Or via the standard env var:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
```

Every `run_scenario`, `verify_proof`, and `canonicalize_value`
call from then on emits spans (`ophamin.scenario.run.<name>`,
`ophamin.proof.verify`, `ophamin.canonical.encode`) and records
metrics (`ophamin_scenarios_run_total`,
`ophamin_scenario_duration_seconds`,
`ophamin_proofs_verified_total`,
`ophamin_canonical_bytes_encoded`).

See [`src/ophamin/observability/README.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/src/ophamin/observability/README.md)
for the full attribute catalogue + sidecar wiring with HTTP /
MCP / CloudEvents.

### "I want my proof on Sigstore / Rekor / SLSA infrastructure."

Wrap the proof as an in-toto Statement v1 (ITE-6), optionally
sealed inside a DSSE envelope:

```python
from ophamin.interop import to_in_toto_statement, to_dsse_envelope

# 1. Bare Statement — for in-process inspection or custom signing
stmt = to_in_toto_statement(signed_proof)
# {
#   "_type": "https://in-toto.io/Statement/v1",
#   "predicateType": "https://github.com/IdirBenSlama/Ophamin/.../SCHEMAS.md#empirical-proof-record-v1",
#   "subject": [{"name": "...", "digest": {"sha256": "<proof_id>"}}],
#   "predicate": {"body": {...}, "signature": "<hmac>"}
# }

# 2. DSSE-sealed envelope — for upload to Rekor or storage in an
#    attestation archive
envelope = to_dsse_envelope(signed_proof, key=b"my-dsse-key", keyid="rsa-2026")
# {
#   "payloadType": "application/vnd.in-toto+json",
#   "payload": "<base64 of canonical Statement JSON>",
#   "signatures": [{"keyid": "rsa-2026", "sig": "<base64 HMAC>"}]
# }
```

The Statement's subject digest IS the proof's content-addressed
`proof_id` (SHA-256 over sections 1–8), so the in-toto subject
is structurally tied to Ophamin's own canonical form. Downstream
verifiers can:

- Run `cosign verify-attestation --type custom` against the
  envelope using `OPHAMIN_PREDICATE_TYPE_V1` as the type-filter.
- Upload to Rekor: `rekor-cli upload --type intoto --artifact envelope.json`.
- Plug into a `policy-controller` admission webhook to gate
  Kubernetes deployments on the presence of a VALIDATED Ophamin
  proof matching the cluster's expected subject digest.

The DSSE PAE (Pre-Authentication Encoding) prevents
signature-substitution across `payloadType`s, per the
secure-systems-lab DSSE spec. `verify_dsse_envelope(env, key)`
checks the outer envelope; the inner Ophamin HMAC over
`predicate.body` is verified separately with the original
Ophamin signing key — two-layer cryptographic trust where the
outer (DSSE) and inner (Ophamin) keys may differ.

See [`src/ophamin/interop/in_toto.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/src/ophamin/interop/in_toto.py)
for the full API. References:

- [in-toto Statement v1 spec](https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md)
- [DSSE spec](https://github.com/secure-systems-lab/dsse)
- [SLSA in-toto integration](https://slsa.dev/blog/2023/05/in-toto-and-slsa)

### "I want my proof packaged for Zenodo / Galaxy / WorkflowHub."

Wrap the proof as an RO-Crate 1.2 (Research Object Crate). Two
APIs exist — the building block returns the metadata dict, and
the convenience wrapper writes a complete crate directory:

```python
from ophamin.interop import write_ro_crate

# One call → complete self-describing crate directory on disk
crate_dir = write_ro_crate(
    signed_proof,
    "./my-empirical-attestation",
    extra_root_metadata={
        "creator": {"@id": "https://orcid.org/0000-0000-0000-0000"},
        "license": {"@id": "https://spdx.org/licenses/Apache-2.0"},
    },
)
# crate_dir is an absolute pathlib.Path to the directory containing
# both proof.json and ro-crate-metadata.json — ready to upload to
# Zenodo, submit to WorkflowHub, ingest into Galaxy, or zip via
# shutil.make_archive(str(crate_dir), "zip", crate_dir).
```

For full control over the metadata-without-write path, use
`to_ro_crate_metadata` directly (returns a dict). `write_ro_crate`
refuses to overwrite an existing directory by default —
`overwrite=True` opts in. Both APIs accept the same `proof_filename`
and `extra_root_metadata` kwargs.

The resulting `./my-empirical-attestation/` directory is a
complete RO-Crate. Upload it to Zenodo (mint a DOI), submit it
to WorkflowHub, or ingest it into Galaxy — the JSON-LD
metadata is self-describing and tools that consume RO-Crate
will pick out the principal artifact (the signed proof),
data references, substrate, verdict, and reproduction command
automatically.

The exporter maps Ophamin's nine sections into schema.org
vocabulary:

- Root `Dataset` (`@id: "./"`) — the crate itself, name +
  datePublished + identifier (the proof's content-addressed
  `proof_id`)
- `File` (`@id: "proof.json"`) — the signed proof JSON
- `Dataset` (one per §4 DatasetRef) — content-addressed,
  carries `url` (source) + `size` (n_records)
- `SoftwareApplication` (`@id: "#substrate-<name>@<commit>"`) —
  the substrate under test
- `AssessAction` (`@id: "#verdict"`) — the §6 verdict, with
  `result` as a `PropertyValue` carrying the observed metric
- `SoftwareSourceCode` (`@id: "#reproduction"`) — the §7
  reproduction command
- `SoftwareApplication` (`@id: "#ophamin"`) — Ophamin itself,
  with `softwareVersion` + `identifier` (git commit)

See [`src/ophamin/interop/ro_crate.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/src/ophamin/interop/ro_crate.py)
for the full API. References:

- [RO-Crate 1.2 specification](https://www.researchobject.org/ro-crate/specification/1.2/)
- [Schema.org vocabulary](https://schema.org/)
- [FAIR data principles](https://www.go-fair.org/fair-principles/)

### "I want Ophamin scenarios in my Airflow / dbt / Spark lineage."

Emit one OpenLineage 2.0 RunEvent per signed proof, then POST it
to a Marquez backend (or any OpenLineage-aware collector):

```python
import requests
from ophamin.interop import to_openlineage_event

event = to_openlineage_event(signed_proof)
requests.post(
    "http://marquez:5000/api/v1/lineage",
    json=event,
    timeout=5,
)
```

The mapping is shaped for live pipeline integration:

- `eventType` — `COMPLETE` for VALIDATED **and** REFUTED outcomes;
  `FAIL` for INCONCLUSIVE. The REFUTED-vs-FAIL distinction matters:
  REFUTED is a real empirical result and MUST NOT trip "job
  failure" alerts; INCONCLUSIVE means the run didn't produce a
  deciding observation.
- `run.runId` — deterministic UUIDv5 derived from `proof_id` via
  the pinned namespace `ec1e6b1c-…-000000000001`. Same proof →
  same runId on any machine, so Marquez dedupes re-emits for free.
- `job.namespace` — defaults to `"ophamin"`; override per
  deployment.
- `job.name` — defaults to the first PillarEvidence's `pillar`
  field (e.g. `"I.cma"`), overridable via `job_name=`.
- `inputs` — one per §4 DatasetRef, with `dataSource` facet
  (URL) + custom `ophamin_dataset` facet (content_hash, n_records).
- `outputs` — exactly one, namespaced `ophamin.proofs`, named with
  the content-addressed `proof_id`, with a `schema` facet
  describing the proof's column shape.
- Custom facets `ophamin_claim` + `ophamin_verdict` carry the §2
  claim + §6 verdict structured payload, plus the §9 HMAC
  signature for cross-attribution.

The deterministic runId is the killer feature: a downstream
pipeline operator can join lineage on proof_id ↔ runId without
maintaining any separate mapping table. Marquez consumers see
each Ophamin scenario as a first-class job in their lineage graph.

See [`src/ophamin/interop/openlineage.py`](https://github.com/IdirBenSlama/Ophamin/blob/main/src/ophamin/interop/openlineage.py)
for the full API. References:

- [OpenLineage 2.0 spec](https://openlineage.io/docs/spec/object-model)
- [Marquez backend](https://github.com/MarquezProject/marquez)
- [Airflow OpenLineage provider](https://airflow.apache.org/docs/apache-airflow-providers-openlineage/)
- [dbt OpenLineage integration](https://openlineage.io/docs/integrations/dbt)

## Cross-layer composition

The layers are designed to compose. A typical pipeline:

```text
[Rust producer]                              [Python verifier]
  CanonicalValue::Object{...}                  HTTP POST /verify
  + sign_canonical                                 │
  + CloudEvents wrap (in Rust if needed,           ▼
    or hand off to Python proxy)             {verified: true, verdict: ...}
       │
       ▼ Kafka topic "ophamin.proofs"
[Kafka consumer pod]
  + unwrap envelope
  + emit span (OTel)
  + forward to verifier service over HTTP
```

The wire-format contract (signed bytes) is the load-bearing
primitive that survives every transport unchanged. The other
four layers transport it.

## Stability contract

The interop layers follow Ophamin's
[API stability contract](STABILITY.md):

- **`@Stable`** — wire format (`SCHEMAS.md` R1–R11), the six
  tool function signatures in `ophamin.interfaces._impls`, MCP
  tool names + arg shapes, HTTP endpoint paths + body shapes,
  CloudEvents attribute names emitted, OTel span names and
  attribute names, in-toto Statement / DSSE constants
  (`IN_TOTO_STATEMENT_V1_TYPE`, `OPHAMIN_PREDICATE_TYPE_V1`,
  `DSSE_INTOTO_PAYLOAD_TYPE`), RO-Crate constants
  (`RO_CRATE_CONTEXT_V1_2`, `RO_CRATE_CONFORMS_TO_V1_2`,
  `DEFAULT_PROOF_FILENAME`, `RO_CRATE_METADATA_FILENAME`),
  OpenLineage constants
  (`OPENLINEAGE_SCHEMA_URL`, `OPENLINEAGE_PRODUCER_URL_BASE`,
  `DEFAULT_NAMESPACE`, `OPHAMIN_RUNID_NAMESPACE`).
- **`@Provisional`** — implementation-internal details (Rust
  module layout under `crates/ophamin-proof/src/`, JS module
  layout under `packages/ophamin-proof-js/src/`, OTel metric
  internals).
- **`@Deprecated`** — none currently. Backward-compat policy
  matches [`SCHEMAS.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/SCHEMAS.md): one-minor-version
  deprecation window before removal.

A drift in any `@Stable` surface is a major-version bump with a
documented migration path.

## Runnable examples

Every layer ships at least one runnable consumer-facing example:

| Layer | Run | What it does |
|---|---|---|
| Wire-format (Python) | `pytest tests/test_canonical_form_fixtures.py` | Validates Python canonical-form encoder against 5 cross-language fixtures |
| Wire-format (Rust) | `cd crates/ophamin-proof && cargo run --example verify_proof`<br>`cargo run --example sign_value` | Loads a shipped proof + verifies HMAC under default key; builds a `CanonicalValue` tree + signs |
| Wire-format (JS) | `cd packages/ophamin-proof-js && npm run example:verify`<br>`npm run example:sign` | Same shape as the Rust examples |
| MCP server | `PYTHONPATH=src python examples/walkthrough_mcp_server.py` | Exercises all 6 MCP tools through FastMCP's in-process `call_tool` |
| HTTP REST API | `PYTHONPATH=src python examples/walkthrough_http_api.py` | Drives 7 endpoints + inspects `/openapi.json` via `TestClient` |
| CloudEvents | `PYTHONPATH=src python examples/walkthrough_cloudevents.py` | Wraps + transit-serializes + unwraps + re-verifies a real shipped proof |
| OpenTelemetry | `PYTHONPATH=src python examples/walkthrough_otel.py` | Installs `InMemoryExporter`, exercises impls, prints captured spans + metrics |

Each script self-asserts its invariants — they exit non-zero on
behavioural drift, so they double as CI smoke pins. See
[`examples/README.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/examples/README.md)
for the full catalogue.

## See also

- [`SCHEMAS.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/SCHEMAS.md) — the normative wire-format spec.
- [`docs/REPRODUCING.md`](REPRODUCING.md) — external-rebuild
  guide for verifying the framework's claims on your own
  infrastructure.
- [`docs/STABILITY.md`](STABILITY.md) — API stability policy.
- Per-layer READMEs:
  - [`crates/ophamin-proof/README.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/crates/ophamin-proof/README.md)
  - [`packages/ophamin-proof-js/README.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/packages/ophamin-proof-js/README.md)
  - [`src/ophamin/mcp/README.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/src/ophamin/mcp/README.md)
  - [`src/ophamin/http_api/README.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/src/ophamin/http_api/README.md)
  - [`src/ophamin/cloudevents/README.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/src/ophamin/cloudevents/README.md)
  - [`src/ophamin/observability/README.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/src/ophamin/observability/README.md)
- [`paper/paper.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/paper/paper.md) — methods paper covering
  the framework's empirical claims.
