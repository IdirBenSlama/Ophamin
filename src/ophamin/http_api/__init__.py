"""Ophamin's HTTP REST API.

Same logical surface as the MCP server (:mod:`ophamin.mcp`), exposed
over HTTP for consumers that don't speak MCP. The shared
implementations live in :mod:`ophamin.interfaces._impls` so behaviour
matches across both transports byte-for-byte.

Endpoints:

- ``GET  /health`` — liveness check.
- ``GET  /version`` — server identity (name / title / framework version).
- ``GET  /scenarios`` — list every scenario in the registry.
- ``GET  /scenarios/{name}/claim`` — get a scenario's falsifiable claim.
- ``POST /verify`` — verify a wire-form signed proof.
- ``POST /canonicalize`` — produce canonical bytes + HMAC for any value.
- ``POST /proofs/index`` — index a directory tree of signed proofs.
- ``POST /scenarios/{name}/run`` — **heavyweight** — run a scenario.

OpenAPI spec auto-generated at ``/docs`` (Swagger UI) and ``/redoc``.

CLI:

    ophamin http serve --host 0.0.0.0 --port 8000

Library:

    from ophamin.http_api import build_app
    app = build_app()
    # mount onto any ASGI server (uvicorn, hypercorn, daphne)

See ``src/ophamin/http_api/README.md`` for curl examples and the
deployment-recipes wiring for popular HTTP clients.
"""

from __future__ import annotations

from ophamin.http_api.server import (
    SERVER_NAME,
    SERVER_TITLE,
    SERVER_VERSION,
    build_app,
)

__all__ = ["build_app", "SERVER_NAME", "SERVER_TITLE", "SERVER_VERSION"]
