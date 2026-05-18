# Ophamin interop overview

> One page covering every way to drive, consume, or observe
> Ophamin from outside Python. Five interop layers stacked so a
> consumer picks the one that fits their shape.

## At a glance

| Consumer shape | Layer | Surface | Read-only? | First shipped |
|---|---|---|---|---|
| Non-Python *systems* needing cryptographic verification | Wire-format ports | `crates/ophamin-proof` (Rust) + `packages/ophamin-proof-js` (JS/TS) — both read AND write | no (write-side since 0.21.0) | `0.16.0` (read), `0.21.0` (write) |
| AI agents speaking MCP | MCP server | `ophamin mcp serve` (stdio / SSE / streamable-http) | one tool writes (`run_scenario`); rest are read | `0.17.0` |
| HTTP / service-style consumers | HTTP REST API | `ophamin http serve` (FastAPI; OpenAPI 3 at `/openapi.json`) | same as MCP | `0.18.0` |
| Event-stream routing infrastructure | CloudEvents 1.0 envelope | `ophamin.cloudevents.wrap` / `unwrap` (Python) | no — wrap is opt-in; routing is read | `0.19.0` |
| Observability backends (Jaeger / Datadog / etc.) | OpenTelemetry instrumentation | `ophamin.observability.setup_otel()` + ambient OTel SDK | n/a (telemetry is one-way) | `0.20.0` |

All five layers wrap the **same shared implementations**
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
  attribute names.
- **`@Provisional`** — implementation-internal details (Rust
  module layout under `crates/ophamin-proof/src/`, JS module
  layout under `packages/ophamin-proof-js/src/`, OTel metric
  internals).
- **`@Deprecated`** — none currently. Backward-compat policy
  matches [`SCHEMAS.md`](https://github.com/IdirBenSlama/Ophamin/blob/main/SCHEMAS.md): one-minor-version
  deprecation window before removal.

A drift in any `@Stable` surface is a major-version bump with a
documented migration path.

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
