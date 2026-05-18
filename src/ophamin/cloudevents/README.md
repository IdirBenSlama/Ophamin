# Ophamin CloudEvents wrapper

> Wrap Ophamin signed proofs in [CloudEvents 1.0](https://github.com/cloudevents/spec)
> structured-mode envelopes so event-stream consumers (Kafka,
> EventBridge, Knative, NATS, anything CloudEvents-aware) can route
> Ophamin records natively.

This is the **fourth interop layer**, alongside:

- **Wire-format** (Rust + JS verifier ports): non-Python *systems*.
- **MCP server** (0.17.x): non-Python *agents*.
- **HTTP REST API** (0.18.0): non-Python *services* over HTTP.
- **CloudEvents wrapper** (0.19.0, this directory): *event streams*.

The wrapper is library-only by design — your event producer
(scenario runner, batch job, MCP handler, ...) calls `wrap()` and
emits the result to whichever sink suits. The wrapper does not
ship a sink adapter; CloudEvents lets you carry the same envelope
shape across every transport.

## Usage

```python
from ophamin.cloudevents import wrap, unwrap
from ophamin.interfaces._impls import run_scenario_impl, verify_proof_impl
import json

# Producer side
summary = run_scenario_impl("spearman-crosscheck", "{}")
# Or: load a full signed proof from disk
proof = json.loads(open("some-proof.json").read())

envelope = wrap(proof, source="urn:my-deployment:ophamin")
# envelope is a dict ready for json.dumps + emit on Kafka / HTTP / SNS / etc.
producer.send_event(json.dumps(envelope))

# Consumer side
envelope_text = await consumer.next_event()
recovered = unwrap(envelope_text)
# recovered is the proof's dict — verify it the usual way
result = verify_proof_impl(json.dumps(recovered))
assert result["verified"]
```

## What's in the envelope

A wrapped proof produces a CloudEvents 1.0 structured-mode JSON
object with these attributes:

| Attribute | Value |
|---|---|
| `specversion` | `"1.0"` |
| `id` | the proof's content-addressed `proof_id` (SHA-256 hex) |
| `source` | caller-supplied URI-reference (`urn:` or `https://`) |
| `type` | default `"dev.ophamin.proof.emitted.v1"` (override via `event_type=`) |
| `time` | from the record's `identity.created_at` (ISO-8601) |
| `datacontenttype` | `"application/json"` |
| `dataschema` | URI pointing at `SCHEMAS.md`'s `EmpiricalProofRecord/1.0` section |
| `ophaminversion` | framework version that emitted the proof |
| `ophaminschema` | record's wire-format `schema_version` |
| `ophaminverdict` | `VALIDATED` / `REFUTED` / `INCONCLUSIVE` |
| `data` | the full proof record (structured mode) |

CloudEvents extension attributes (`ophamin*`) follow the [§3.1
naming rule](https://github.com/cloudevents/spec/blob/main/cloudevents/spec.md#attribute-naming-convention):
lowercase letters + digits, no separators, ≤ 20 chars.

## Custom extension attributes

```python
envelope = wrap(
    proof,
    source="urn:my-deployment:ophamin",
    event_type="dev.ophamin.proof.refuted.v1",
    extra_extensions={
        "trace": "abc123",
        "deployment": "prod",
    },
)
```

Extension-attribute rules (enforced loud-failure):
- Name MUST match `^[a-z0-9]{1,20}$` (CloudEvents §3.1).
- Value MUST be a string.
- Name MUST NOT collide with a built-in CloudEvents attribute
  (`specversion`, `id`, `source`, `type`, `time`,
  `datacontenttype`, `dataschema`, `data`) or any of Ophamin's
  emitted extensions (`ophaminversion`, `ophaminschema`,
  `ophaminverdict`).

## Routing strategies

CloudEvents-aware consumers can route on `type`:

```text
dev.ophamin.proof.emitted.v1     → all Ophamin proofs
dev.ophamin.proof.refuted.v1     → only REFUTED verdicts (caller-set type)
dev.ophamin.proof.validated.v1   → only VALIDATED verdicts
```

Or filter on Ophamin extensions:

```text
ophaminverdict = "REFUTED"       → REFUTED verdicts regardless of type
ophaminschema  = "1.0"           → only schema-v1.0 records
```

The wrapper does not pre-filter — the producer emits one envelope
per proof and consumers filter in their routing layer.

## Kafka recipe

```python
from confluent_kafka import Producer
from ophamin.cloudevents import wrap
import json

p = Producer({"bootstrap.servers": "localhost:9092"})

def on_proof_ready(proof):
    envelope = wrap(proof, source="urn:my-deployment:ophamin")
    # CloudEvents on Kafka — structured mode = single JSON value
    p.produce("ophamin.proofs", value=json.dumps(envelope).encode("utf-8"))
```

For Kafka **binary mode** (each CloudEvents attribute as a Kafka
header) — that's a separate spec section the wrapper doesn't ship
today; structured mode is the load-bearing format because it
survives every transport unchanged. Binary mode is future work.

## EventBridge recipe

```python
import boto3
from ophamin.cloudevents import wrap
import json

events = boto3.client("events")

def emit_to_eventbridge(proof):
    envelope = wrap(proof, source="urn:my-deployment:ophamin")
    events.put_events(Entries=[{
        "Source": envelope["source"],
        "DetailType": envelope["type"],
        "Detail": json.dumps(envelope),
        "EventBusName": "default",
    }])
```

## Verifying signatures on the consumer side

The wrapper does NOT verify signatures — that's the consumer's
responsibility (and rightly so: a consumer may want to verify
against its own deployment-specific key, not the default key).

```python
from ophamin.cloudevents import unwrap
from ophamin.interfaces._impls import verify_proof_impl

def handle_event(envelope_json):
    proof = unwrap(envelope_json)
    result = verify_proof_impl(
        json.dumps(proof),
        sign_key_b64=my_deployment_key_b64,
    )
    if not result["verified"]:
        log.warning("tampered proof: %s", envelope_json["id"])
        return
    # proof is trusted from here
    ...
```

Cross-language consumers can pass the unwrapped proof to the Rust
`ophamin-proof` or JS `@ophamin/proof` verifier — the wrapper does
nothing to the embedded record, so all three verifier ports apply.

## Spec compliance

The wrapper targets [CloudEvents 1.0](https://github.com/cloudevents/spec/releases/tag/v1.0)
exactly. The validator (`validate_envelope`) checks the §3.1
REQUIRED attributes (`specversion`, `id`, `source`, `type`); the
`unwrap` function calls the validator before extracting the proof.

A wrapped envelope passes the CloudEvents 1.0 JSON Schema (subject
to the proof's `data` content being a valid JSON object — which
every Ophamin signed proof is by construction).

## See also

- [CloudEvents 1.0 spec](https://github.com/cloudevents/spec/blob/main/cloudevents/spec.md)
- [`SCHEMAS.md`](../../../SCHEMAS.md) — normative wire-format spec
  for the embedded record.
- [`src/ophamin/interfaces/_impls.py`](../interfaces/_impls.py) —
  the shared `verify_proof_impl` to verify the unwrapped proof.
- [`src/ophamin/http_api/README.md`](../http_api/README.md) — the
  parallel HTTP REST interop surface.
