# Ophamin HTTP REST API

> Expose Ophamin's read + run + verify surfaces over HTTP so any
> consumer that speaks JSON over HTTP — Kubernetes microservices,
> browser apps, curl scripts, language SDKs without an MCP
> implementation — can drive scenarios and verify signed proofs.

This is the **third interop layer**, alongside:

- **Wire-format** (`SCHEMAS.md` + `crates/ophamin-proof` + `packages/ophamin-proof-js`): non-Python systems verify Python-emitted records.
- **MCP server** (`src/ophamin/mcp/`): non-Python agents drive scenarios.
- **HTTP REST API** (this directory, 0.18.0): non-Python services use HTTP.

The HTTP server and the MCP server **wrap the same shared
implementations** (`src/ophamin/interfaces/_impls.py`), so behavioural
drift between the two is structurally impossible.

## Endpoint catalogue

| Method | Path | Summary | Read-only |
|---|---|---|---|
| `GET` | `/health` | Liveness check (always 200). | ✓ |
| `GET` | `/version` | Server identity + framework version. | ✓ |
| `GET` | `/scenarios` | Enumerate every registered scenario. | ✓ |
| `GET` | `/scenarios/{name}/claim` | Get a scenario's falsifiable claim. | ✓ |
| `POST` | `/verify` | Verify a wire-form signed proof. Body: `{proof_json, sign_key_b64?}`. | ✓ |
| `POST` | `/canonicalize` | Canonical UTF-8 bytes + HMAC for any value. Body: `{value_json, sign_key_b64?}`. | ✓ |
| `POST` | `/proofs/index` | Walk a server-side directory. Body: `{directory}`. | ✓ |
| `POST` | `/scenarios/{name}/run` | **Heavyweight** — run a scenario. Body: `{kwargs_json?}`. | ✗ |
| `GET` | `/metrics` | Prometheus text exposition. | ✓ |
| `GET` | `/proofs/bundles/tree` | Walk `proofs/` as nested tier→scenario→bundles. | ✓ |
| `GET` | `/proofs/bundles/file` | Serve one file from inside a proof bundle. | ✓ |
| `GET` | `/openapi.json` | OpenAPI 3.x spec, FastAPI-generated. | ✓ |
| `GET` | `/docs` | Swagger UI, interactive. | ✓ |
| `GET` | `/redoc` | ReDoc, alternative renderer. | ✓ |
| `GET` | `/ui` | Provisional read-mostly SPA (vanilla JS, no build). | ✓ |
| `GET` | `/app` | **Ophamin Console** — the React GUI (no build step). | ✓ |

## Browser GUIs

Two browser surfaces ship with the server, both served from the same
origin as the REST API (no CORS, no separate deploy):

- **`/app` — the Ophamin Console.** The production GUI: a UniFi-styled
  React single-page app (React 18 + Babel-standalone, compiled in the
  browser — no build step). Eighteen screens; Overview, Proofs,
  Scenarios, Run, and Telemetry **live-wire** to the REST surface above
  (the Proofs detail view renders the real signed `proof.json`), and the
  rest render grounded illustrative state. Falls back to the bundled mock
  per-endpoint when a fetch fails, so it renders against a live server, a
  fresh instance with no proofs yet, or straight off disk.
- **`/ui` — the provisional SPA.** A lighter vanilla-HTML/JS/CSS app that
  browses scenarios + the proof bundle tree + the `/metrics` exposition.
  Kept alongside `/app`. `GET /` redirects here.

Both stamp their static assets with a `?v=<version>` cache-buster and
serve their HTML `no-store`, so an upgrading browser never pairs new HTML
with stale, cached JS. Neither GUI puts an external LLM in the
measurement path — they are read-mostly views over the signed-proof
surface plus the one state-changing `Run` action.

## Starting the server

CLI (uvicorn-backed):

```bash
# Bind localhost:8000
ophamin http serve

# Bind all interfaces on port 80
ophamin http serve --host 0.0.0.0 --port 80

# Multiple workers for production
ophamin http serve --host 0.0.0.0 --port 8000 --workers 4

# Verbose logging
ophamin http serve --log-level debug
```

As a library (mount onto your own ASGI server):

```python
from ophamin.http_api import build_app

app = build_app()
# uvicorn or hypercorn or your existing app
```

## curl examples

Replace `localhost:8000` with your actual server address.

### Liveness probe

```bash
curl -s http://localhost:8000/health
# {"status":"ok"}
```

### Server identity

```bash
curl -s http://localhost:8000/version | jq .
```

### List scenarios

```bash
curl -s http://localhost:8000/scenarios | jq '.scenarios[] | .name'
```

### Get a scenario's claim

```bash
curl -s http://localhost:8000/scenarios/spearman-crosscheck/claim | jq .claim
```

### Verify a signed proof

```bash
PROOF_JSON=$(cat proofs/measurement_machinery/spearman_cross_framework/spearman_scipy_vs_pingouin_f65319cb2ab7eb3d.json)
curl -s -X POST http://localhost:8000/verify \
    -H "Content-Type: application/json" \
    -d "$(jq -n --arg p "$PROOF_JSON" '{proof_json: $p}')" | jq .
# {"verified": true, "proof_id": "...", "verdict": {...}, ...}
```

### Canonicalize a value

```bash
curl -s -X POST http://localhost:8000/canonicalize \
    -H "Content-Type: application/json" \
    -d '{"value_json": "{\"x\": 30, \"y\": 30.0}"}' | jq .
# {"canonical": "{\"x\":30,\"y\":30.0}", "sha256_hex": "...", "hmac_sha256_hex": "..."}
```

Note: `"x": 30` (int) emits as `30` (no `.0`) while `"y": 30.0`
(float) emits as `30.0` — exactly what the wire-format contract
guarantees per `SCHEMAS.md` R4 / R5.

### Index a directory of proofs

```bash
curl -s -X POST http://localhost:8000/proofs/index \
    -H "Content-Type: application/json" \
    -d '{"directory": "/var/ophamin/proofs"}' | jq .
```

### Run a scenario (heavyweight)

```bash
curl -s -X POST http://localhost:8000/scenarios/spearman-crosscheck/run \
    -H "Content-Type: application/json" \
    -d '{"kwargs_json": "{\"n_pairs\": 10, \"sample_size\": 50}"}' | jq .
# {"scenario": "spearman-crosscheck", "verdict": {"outcome": "VALIDATED", ...}, ...}
```

## Deployment

### Docker

```dockerfile
FROM python:3.12-slim

RUN pip install --no-cache-dir 'ophamin[all]'

EXPOSE 8000
CMD ["ophamin", "http", "serve", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ophamin-http-api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: ophamin-http-api
  template:
    metadata:
      labels:
        app: ophamin-http-api
    spec:
      containers:
        - name: ophamin
          image: your-registry/ophamin:0.18.0
          ports:
            - containerPort: 8000
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 2
            periodSeconds: 5
```

`/health` is deliberately cheap (no backend touch) so it's a safe
liveness/readiness probe target.

### systemd

```ini
[Unit]
Description=Ophamin HTTP API
After=network.target

[Service]
Type=simple
User=ophamin
ExecStart=/usr/local/bin/ophamin http serve --host 0.0.0.0 --port 8000
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

## Authentication / authorization

**The server has no built-in auth.** It's designed to be deployed
behind a reverse proxy / ingress that handles authentication
(nginx + basic auth, Traefik + OIDC, API Gateway with IAM, etc.).
Production deployments MUST gate the heavyweight `/scenarios/{name}/run`
endpoint — running scenarios is the one tool that costs compute
proportional to caller demand.

If you need finer-grained auth (per-scenario, per-key) the right
place to add it is in a middleware layer above `build_app()`:

```python
from fastapi import Depends
from ophamin.http_api import build_app

def verify_api_key(...) -> None:
    ...

app = build_app()
# Add middleware or per-route dependencies here.
```

The shared implementations (`ophamin.interfaces._impls`) are
deliberately auth-agnostic — they accept signing-key bytes as
arguments rather than fetching them from a global. This keeps the
auth surface attachable at any layer above.

## Why this matters (interop reframe)

Together with the MCP server (`ophamin mcp serve`) and the
cross-language verifier ports, Ophamin is now reachable from:

- **Any language** that can verify a signed record (Python natively;
  Rust + JS shipped; future ports against the cross-language
  fixtures).
- **Any agent** that speaks MCP (Claude Code, Claude Desktop,
  Cursor, Cline, custom orchestrators).
- **Any service** that speaks JSON over HTTP (Kubernetes
  microservices, browser apps, curl scripts, language SDKs
  without an MCP implementation).

A consumer that can't (or won't) take a Python dependency now has
multiple ways to drive Ophamin: a cryptographic verifier in their
own language (read-only), an MCP client (agent-callable), or an
HTTP API (any service-style consumer).

## See also

- [`SCHEMAS.md`](../../../SCHEMAS.md) — normative wire-format spec the
  `/verify` + `/canonicalize` endpoints implement.
- [`src/ophamin/mcp/README.md`](../mcp/README.md) — the MCP server
  (parallel surface).
- [`packages/ophamin-proof-js/README.md`](../../../packages/ophamin-proof-js/README.md) — JS/TS read-only verifier.
- [`crates/ophamin-proof/README.md`](../../../crates/ophamin-proof/README.md) — Rust read-only verifier.
