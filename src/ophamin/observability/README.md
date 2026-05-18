# Ophamin OpenTelemetry observability

> Instrument Ophamin scenario execution + proof verification with
> OpenTelemetry spans and metrics. Any OTel-compatible backend —
> Jaeger, Zipkin, Tempo, Grafana, Datadog, New Relic, Honeycomb,
> GCP Cloud Trace, AWS X-Ray, Azure Monitor — can collect and
> visualize what Ophamin is doing in production.

This is the **fifth interop layer**:

| Layer | Surface | Shipped |
|---|---|---|
| Wire-format | Rust + JS verifier ports | 0.16.0 |
| Agents | MCP server (`ophamin mcp serve`) | 0.17.0 |
| Services | HTTP REST API (`ophamin http serve`) | 0.18.0 |
| Event streams | CloudEvents wrapper | 0.19.0 |
| **Observability** | OpenTelemetry spans + metrics | **0.20.0** |

The instrumentation is **always-on at the API surface** but
**no-op when no SDK provider is configured**. The OpenTelemetry API
returns proxy tracers and meters by default; calling
`start_as_current_span` on a proxy is a near-free operation
(~100 ns per call, dominated by attribute construction). The cost
when nothing is exporting is negligible.

## What gets instrumented

The shared transport-agnostic implementations
(`ophamin.interfaces._impls`) emit spans + metrics:

| Function | Span name | Key attributes |
|---|---|---|
| `run_scenario_impl` | `ophamin.scenario.run.<name>` | `ophamin.scenario.name`, `ophamin.scenario.family`, `ophamin.scenario.tier`, `ophamin.scenario.target`, `ophamin.verdict.outcome`, `ophamin.verdict.observed_value`, `ophamin.proof.id` |
| `verify_proof_impl` | `ophamin.proof.verify` | `ophamin.proof.verified` (bool), `ophamin.proof.id`, `ophamin.verdict.outcome` |
| `canonicalize_value_impl` | `ophamin.canonical.encode` | `ophamin.canonical.bytes` |

Since the MCP server, HTTP REST API, and any future transport all
wrap the same shared impls, **every consumer surface gets the same
spans automatically** without per-transport instrumentation.

Metrics:

| Name | Type | Unit | Labels |
|---|---|---|---|
| `ophamin_scenarios_run_total` | Counter | 1 | `scenario`, `family`, `tier`, `outcome` |
| `ophamin_scenario_duration_seconds` | Histogram | s | `scenario`, `family` |
| `ophamin_proofs_verified_total` | Counter | 1 | `verified`, `outcome` |
| `ophamin_canonical_bytes_encoded` | Histogram | bytes | (none) |

## Quick start: print spans + metrics to stderr

```python
from ophamin.observability import setup_otel

# Local dev — print everything to stderr
setup_otel(enable_console_exporter=True)

# Now run any Ophamin scenario / verify / canonicalize call;
# spans + metrics print to stderr.
from ophamin.interfaces._impls import run_scenario_impl
run_scenario_impl("spearman-crosscheck", "{}")
```

## Production: ship to an OTLP collector

```python
from ophamin.observability import setup_otel

# Ship to an OTLP HTTP collector
setup_otel(otlp_endpoint="http://otel-collector.observability:4318")
```

Or via env var (standard OpenTelemetry convention):

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
python -c "from ophamin.observability import setup_otel; setup_otel()"
```

The env-var pattern integrates naturally with Kubernetes downward
API + service mesh sidecar injection — the OTLP endpoint lives in
your deployment config, not in your code.

## Wiring with the HTTP REST API

```python
# In your app's entry point, BEFORE `ophamin http serve`:
from ophamin.observability import setup_otel
setup_otel(otlp_endpoint="http://otel-collector:4318")
```

Or as a sidecar to the CLI:

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318 \
OTEL_SERVICE_NAME=ophamin-http \
python -c "
from ophamin.observability import setup_otel
setup_otel()
" && \
ophamin http serve --host 0.0.0.0 --port 8000
```

## Wiring with the MCP server

Same pattern — call `setup_otel()` before `mcp.run()`:

```python
from ophamin.observability import setup_otel
from ophamin.mcp import build_server

setup_otel(otlp_endpoint="http://otel-collector:4318")
mcp = build_server()
mcp.run(transport="stdio")
```

## Combining with CloudEvents

The CloudEvents wrapper is observability-aware indirectly: every
`verify_proof_impl` call inside an event-stream consumer emits a
span. So a Kafka consumer pipeline that wraps proofs at production
+ unwraps + verifies at consumption produces TWO spans linked via
the same `ophamin.proof.id` attribute — pre and post the transit.

```text
[producer pod] ophamin.canonical.encode  → wraps
   ↓ Kafka transit
[consumer pod] ophamin.proof.verify      → unwraps + verifies
```

Both spans carry `ophamin.proof.id` so they can be joined in your
trace backend.

## Custom instrumentation (your own substrate adapter)

If you're writing a custom `SubstrateUnderTest` adapter and want
its sub-operations to nest inside Ophamin's scenario span:

```python
from ophamin.observability import get_tracer

tracer = get_tracer()

def my_substrate_cycle():
    with tracer.start_as_current_span("ophamin.substrate.cycle"):
        # This span becomes a child of the surrounding
        # ophamin.scenario.run.<name> span automatically (OTel
        # uses thread-local context to maintain the call stack).
        do_work()
```

## Span semantics

| Verdict outcome | Span status |
|---|---|
| `VALIDATED` | `OK` |
| `INCONCLUSIVE` | `OK` (the scenario completed normally) |
| `REFUTED` | `OK` (refutation is a successful experimental outcome) |
| Exception during run | `ERROR`, exception recorded |

The framework's view: a `REFUTED` verdict means the experiment
worked — the hypothesis was falsified. That's not a system error,
even if it's the result the consumer cares about. Span status
`ERROR` is reserved for cases where the scenario could not complete
(unhandled exception, resource exhaustion, etc.).

For backends that want to alert on `REFUTED` regardless: filter on
the `ophamin.verdict.outcome` attribute, not on the span status.

## Required pip extras

The `[telemetry]` extra installs:

- `opentelemetry-api>=1.20`
- `opentelemetry-sdk>=1.20`
- `prometheus_client>=0.17` (for the Prometheus probe path,
  unrelated to this OTel module but in the same extra)

Plus, for `setup_otel(otlp_endpoint=...)`:

- `opentelemetry-exporter-otlp-proto-http` (commonly bundled
  with `opentelemetry-sdk` distributions)

`ophamin.observability.get_tracer` and `get_meter` work without
the `[telemetry]` extra (the OTel API package alone provides the
no-op proxies). Only `setup_otel` needs the SDK packages.

## See also

- [OpenTelemetry semantic conventions](https://opentelemetry.io/docs/specs/semconv/)
- [`src/ophamin/interfaces/_impls.py`](../interfaces/_impls.py) —
  the shared functions that emit the spans.
- [`src/ophamin/cloudevents/README.md`](../cloudevents/README.md) —
  CloudEvents wrapper (event-stream interop).
- [`src/ophamin/http_api/README.md`](../http_api/README.md) — HTTP
  REST API (the typical place to wire `setup_otel`).
