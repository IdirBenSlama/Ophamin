"""FastAPI app exposing Ophamin's read + run + verify surfaces over HTTP.

Same logical surface as the MCP server (:mod:`ophamin.mcp`); both
wrap the shared implementations from :mod:`ophamin.interfaces._impls`
so behaviour matches across transports.

The app is purely a thin transport wrapper. All load-bearing logic
lives in the shared impls module; this file routes HTTP requests
to it and shapes the responses for FastAPI's OpenAPI generator.
"""

from __future__ import annotations

import re
from typing import Any

from pathlib import Path as _Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
)
from fastapi.staticfiles import StaticFiles
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Gauge,
    Info,
    generate_latest,
)
from pydantic import BaseModel, Field

from ophamin import __version__
from ophamin.http_api.bundle_browser import (
    ALLOWED_BUNDLE_FILES,
    BundlePathError,
    bundle_tree,
    safe_bundle_file_path,
)
from ophamin.http_api.metrics import (
    METRICS,
    http_metrics_middleware_factory,
    render_exposition,
)
from ophamin.interfaces._impls import (
    canonicalize_value_impl,
    get_scenario_claim_impl,
    list_scenarios_impl,
    read_proof_index_impl,
    run_scenario_impl,
    verify_proof_impl,
)
from ophamin.measuring.scenarios import SCENARIOS

#: Path to the bundled static-asset directory (index.html + app.js + styles.css)
#: served at `/ui/` when the SPA is enabled.
_STATIC_DIR: _Path = _Path(__file__).parent / "static"

#: Path to the React "Ophamin Console" bundle (Claude Design export:
#: index.html + app/*.jsx + app/styles.css + app/data.js) served at
#: `/app` when present. React + Babel-standalone in-browser, no build
#: step — matches the framework's no-build GUI philosophy. The five
#: backed screens (Overview / Proofs / Scenarios / Run / Telemetry)
#: live-wire to the REST surface via data.js's hydrate(); the rest
#: render grounded illustrative state.
_CONSOLE_DIR: _Path = _Path(__file__).parent / "console"

#: Rewrites the design bundle's relative asset refs (``src/href="app/…"``)
#: to absolute ``/app/static/app/…`` with a per-version cache-buster.
_CONSOLE_ASSET_RE = re.compile(r'(src|href)="app/([^"]+)"')

#: MIME-type lookup for the five canonical bundle files. Browsers render
#: HTML / PDF / plain-text natively; JSON / Markdown / LaTeX are served
#: as text so the SPA can fetch + render them in-page.
_BUNDLE_FILE_MEDIATYPE: dict[str, str] = {
    "proof.json": "application/json",
    "proof.md": "text/markdown; charset=utf-8",
    "proof.html": "text/html; charset=utf-8",
    "proof.tex": "text/x-tex; charset=utf-8",
    "proof.pdf": "application/pdf",
}

#: Media types for bundle assets (charts referenced by proof.md). Keyed
#: by lowercased extension. Derived explicitly rather than via the
#: stdlib `mimetypes` module so the surface is deterministic across
#: platforms (mimetypes reads OS-specific /etc/mime.types).
_ASSET_MEDIATYPE: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def _bundle_file_media_type(filename: str) -> str:
    """Pick the media type for a bundle file or asset by name."""
    if filename in _BUNDLE_FILE_MEDIATYPE:
        return _BUNDLE_FILE_MEDIATYPE[filename]
    # asset: derive from extension
    dot = filename.rfind(".")
    if dot != -1:
        ext = filename[dot:].lower()
        if ext in _ASSET_MEDIATYPE:
            return _ASSET_MEDIATYPE[ext]
    return "application/octet-stream"

#: Public server identity. Reused by ``ophamin.http_api.__init__`` and the CLI.
SERVER_NAME: str = "ophamin-http-api"
SERVER_TITLE: str = "Ophamin HTTP REST API"
SERVER_VERSION: str = __version__


# --------------------------------------------------------------------------
# Request body models — FastAPI uses these to generate OpenAPI schemas.
# Response bodies stay as plain ``dict[str, Any]`` since the shared
# impls return rich structured data that doesn't fit a fixed schema
# cleanly (verdict / threshold shapes vary by scenario).
# --------------------------------------------------------------------------


class VerifyRequest(BaseModel):
    """Body of ``POST /verify``."""

    proof_json: str = Field(
        ...,
        description=(
            "The wire-form JSON text of an EmpiricalProofRecord. "
            "Submit the exact bytes of the .json file."
        ),
        examples=['{"schema_version": "1.0", ...}'],
    )
    sign_key_b64: str = Field(
        default="",
        description=(
            "Base64-encoded signing key (default: framework-wide "
            "DEFAULT_SIGN_KEY)."
        ),
    )


class CanonicalizeRequest(BaseModel):
    """Body of ``POST /canonicalize``."""

    value_json: str = Field(
        ...,
        description="JSON-encoded value to canonicalize.",
        examples=['{"x": 30, "y": 30.0}'],
    )
    sign_key_b64: str = Field(
        default="",
        description="Base64-encoded signing key (default: DEFAULT_SIGN_KEY).",
    )


class ProofIndexRequest(BaseModel):
    """Body of ``POST /proofs/index``."""

    directory: str = Field(
        ...,
        description=(
            "Server-side filesystem path to walk. Must exist on the "
            "server hosting this API."
        ),
        examples=["/var/ophamin/proofs"],
    )


class RunScenarioRequest(BaseModel):
    """Body of ``POST /scenarios/{name}/run``."""

    kwargs_json: str = Field(
        default="{}",
        description=(
            "JSON-encoded dict of constructor kwargs (e.g. "
            "``{\"n_pairs\": 10, \"sample_size\": 50}``). Pass an empty "
            "object for default construction."
        ),
        examples=['{"n_pairs": 10, "sample_size": 50}'],
    )


# --------------------------------------------------------------------------
# build_app() — assemble the FastAPI app with all routes registered.
# --------------------------------------------------------------------------


def build_app() -> FastAPI:
    """Construct and return a configured FastAPI app.

    Returns:
        A FastAPI instance with all routes registered. The caller is
        responsible for serving it (e.g. via uvicorn).
    """
    app = FastAPI(
        title=SERVER_TITLE,
        version=SERVER_VERSION,
        description=(
            "Ophamin's HTTP REST API. Same logical surface as the MCP "
            "server (`ophamin mcp serve`) but exposed over HTTP for "
            "consumers that don't speak MCP — microservices, "
            "containerized verifiers, browser apps, anything that "
            "speaks JSON over HTTP. See SCHEMAS.md for the wire-format "
            "contract behind the verify + canonicalize endpoints."
        ),
        contact={"name": "Ophamin", "url": "https://github.com/IdirBenSlama/Ophamin"},
        license_info={"name": "MIT"},
    )

    # ------------------------------------------------------------------
    # Lifecycle / metadata
    # ------------------------------------------------------------------

    @app.get(
        "/health",
        summary="Liveness check",
        description=(
            "Returns 200 if the server is alive. Use as a Kubernetes "
            "readiness/liveness probe target. Always returns "
            "``{\"status\": \"ok\"}`` — does not exercise any backend."
        ),
        tags=["lifecycle"],
    )
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get(
        "/version",
        summary="Server identity",
        description=(
            "Returns the framework version + server name + title. "
            "Useful for clients to verify they're talking to the "
            "expected Ophamin release."
        ),
        tags=["lifecycle"],
    )
    def version() -> dict[str, str]:
        return {
            "name": SERVER_NAME,
            "title": SERVER_TITLE,
            "framework_version": SERVER_VERSION,
        }

    @app.get(
        "/metrics",
        summary="Prometheus exposition",
        description=(
            "Returns Ophamin runtime metrics in the Prometheus text "
            "exposition format. Each call builds a fresh registry — "
            "stateless gauges only, no in-process counter accumulation "
            "(scenario runs are short-lived; cross-pod aggregation "
            "happens at the Prometheus layer). The Helm chart's "
            "ServiceMonitor / PodMonitor templates scrape this path."
        ),
        tags=["lifecycle"],
        response_class=PlainTextResponse,
        responses={
            200: {
                "content": {CONTENT_TYPE_LATEST: {}},
                "description": "Prometheus text exposition.",
            },
        },
    )
    def metrics() -> PlainTextResponse:
        # Delegates to ophamin.http_api.metrics.render_exposition which
        # combines the module-level stateful registry (HTTP request
        # counters, scenario run counters, etc.) with the per-scrape
        # stateless registry (bundle counts, psutil readings, etc.).
        body, content_type = render_exposition()
        return PlainTextResponse(body.decode("utf-8"), media_type=content_type)

    # Register the HTTP metrics middleware. Must be added BEFORE any
    # request handler runs — the @app.middleware decorator on the
    # already-constructed FastAPI app registers it for every future
    # request. Skips /metrics + /ui/static/ paths internally to avoid
    # recursive accounting + label-cardinality explosion.
    app.middleware("http")(http_metrics_middleware_factory())

    # ------------------------------------------------------------------
    # Read endpoints
    # ------------------------------------------------------------------

    @app.get(
        "/scenarios",
        summary="List every scenario in the registry",
        description=(
            "Enumerate every Ophamin scenario with its metadata "
            "(name / family / tier / target / goal / method). "
            "Mirrors the MCP server's ``list_scenarios`` tool."
        ),
        tags=["scenarios"],
    )
    def get_scenarios() -> dict[str, Any]:
        return list_scenarios_impl()

    @app.get(
        "/scenarios/{name}/claim",
        summary="Get a scenario's falsifiable claim",
        description=(
            "Return a scenario's pre-registered falsifiable-claim "
            "five-tuple (statement / operationalization / threshold "
            "/ H0 / H1) + its metadata. Mirrors the MCP server's "
            "``get_scenario_claim`` tool."
        ),
        responses={
            404: {"description": "Scenario not in the registry"},
        },
        tags=["scenarios"],
    )
    def get_scenario_claim(name: str) -> dict[str, Any]:
        try:
            return get_scenario_claim_impl(name)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    # ------------------------------------------------------------------
    # Verify / canonicalize endpoints
    # ------------------------------------------------------------------

    @app.post(
        "/verify",
        summary="Verify a wire-form signed proof",
        description=(
            "Parse a wire-form ``EmpiricalProofRecord`` and HMAC-verify "
            "the signature. Does NOT raise on signature mismatch — "
            "returns ``verified: False`` instead so callers can "
            "introspect verdict fields even on tampered records. "
            "Mirrors the MCP server's ``verify_proof`` tool."
        ),
        responses={
            400: {"description": "Malformed proof JSON or invalid sign-key"},
        },
        tags=["verify"],
    )
    def verify(body: VerifyRequest) -> dict[str, Any]:
        try:
            return verify_proof_impl(body.proof_json, body.sign_key_b64)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/canonicalize",
        summary="Produce canonical bytes + HMAC for any JSON value",
        description=(
            "Implements SCHEMAS.md R1–R11 byte-for-byte (lexicographic "
            "key sort + ensure_ascii=True string escapes + Python-repr "
            "float formatting). Returns canonical bytes + SHA-256 + "
            "HMAC-SHA256 under the given (or default) signing key. "
            "Mirrors the MCP server's ``canonicalize_value`` tool."
        ),
        responses={
            400: {"description": "Malformed value JSON or invalid sign-key"},
        },
        tags=["canonical-form"],
    )
    def canonicalize(body: CanonicalizeRequest) -> dict[str, Any]:
        try:
            return canonicalize_value_impl(body.value_json, body.sign_key_b64)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/proofs/index",
        summary="Index a directory tree of signed proofs",
        description=(
            "Walk a server-side directory tree and return per-scenario "
            "counts + verdict distribution. Does NOT verify signatures "
            "(use ``POST /verify`` per record for that). Mirrors the "
            "MCP server's ``read_proof_index`` tool. Note: the "
            "directory path is server-side, NOT a path on the calling "
            "client's filesystem."
        ),
        responses={
            400: {"description": "Directory not found or not a directory"},
        },
        tags=["verify"],
    )
    def index_proofs(body: ProofIndexRequest) -> dict[str, Any]:
        try:
            return read_proof_index_impl(body.directory)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # ------------------------------------------------------------------
    # Heavyweight: run a scenario
    # ------------------------------------------------------------------

    @app.post(
        "/scenarios/{name}/run",
        summary="Run a scenario (heavyweight; may take minutes)",
        description=(
            "**WARNING: heavyweight.** Construct + run a scenario with "
            "the given JSON-encoded kwargs and return a summary of the "
            "resulting signed proof. Some scenarios run for tens of "
            "seconds; some run for minutes. Use sparingly and consider "
            "running asynchronously via an upstream task queue. The "
            "full proof is NOT returned (only a structured summary); "
            "persist server-side if you need the full record. Mirrors "
            "the MCP server's ``run_scenario`` tool."
        ),
        responses={
            400: {"description": "Unknown scenario or malformed kwargs"},
        },
        tags=["scenarios"],
    )
    def run_scenario(name: str, body: RunScenarioRequest) -> dict[str, Any]:
        try:
            return run_scenario_impl(name, body.kwargs_json)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # ------------------------------------------------------------------
    # Bundle browser — bundle-aware surface for the provisional SPA
    # (read-only). Sits alongside the legacy /proofs/index endpoint;
    # the SPA prefers /proofs/bundles/tree because it returns the
    # nested tier→scenario→bundle shape directly.
    # ------------------------------------------------------------------

    @app.get(
        "/proofs/bundles/tree",
        summary="Walk the proofs/ tree as nested tier→scenario→bundles",
        description=(
            "Returns the 0.59.0 bundle layout as a navigable tree. Each "
            "leaf carries `date`, `verdict`, `short_hash`, `path` "
            "(relative), and the list of files present "
            "(proof.{json,md,html,tex,pdf}). Backs the SPA's left-side "
            "navigation. Caller-side optional `?proofs_root=` override "
            "lets the SPA browse a non-default tree."
        ),
        tags=["proofs"],
    )
    def get_bundle_tree(proofs_root: str = "proofs") -> dict[str, Any]:
        return bundle_tree(proofs_root)

    @app.get(
        "/proofs/bundles/file",
        summary="Serve a single file from inside a proof bundle",
        description=(
            "Read-only file fetch. Path components (`tier`, `scenario`, "
            "`bundle`) and `filename` are validated against strict "
            "regexes; `filename` must be one of "
            "`proof.{json,md,html,tex,pdf}`. Refuses traversal + symlink "
            "escapes. The MIME type is chosen by filename so the browser "
            "renders HTML/PDF natively + the SPA can fetch JSON/MD/TEX as "
            "text for in-page rendering."
        ),
        responses={
            400: {"description": "Malformed path component or refused filename"},
            404: {"description": "Bundle file not found"},
        },
        tags=["proofs"],
    )
    def get_bundle_file(
        tier: str,
        scenario: str,
        bundle: str,
        filename: str,
        proofs_root: str = "proofs",
    ) -> FileResponse:
        try:
            path = safe_bundle_file_path(
                proofs_root, tier, scenario, bundle, filename,
            )
        except BundlePathError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return FileResponse(
            path,
            media_type=_bundle_file_media_type(filename),
            filename=filename,
            # `inline` so proof.html / proof.pdf RENDER inside the GUI's
            # iframe instead of triggering a browser download. Passing
            # `filename=` alone defaults the disposition to `attachment`,
            # which blanks the iframe (the browser downloads rather than
            # displays). The docstring's "renders HTML/PDF natively"
            # contract depends on this. JSON/MD/TEX are fetched via
            # fetch() so the disposition is moot for them; inline is
            # harmless there and keeps one code path.
            content_disposition_type="inline",
        )

    # ------------------------------------------------------------------
    # Provisional GUI — single-page HTML app served from static/
    # ------------------------------------------------------------------

    if _STATIC_DIR.is_dir():
        app.mount(
            "/ui/static",
            StaticFiles(directory=str(_STATIC_DIR)),
            name="ophamin-ui-static",
        )

        @app.get(
            "/ui",
            summary="Provisional read-mostly GUI",
            description=(
                "Serves the bundled single-page HTML app that browses "
                "scenarios + the proofs/ bundle tree + the /metrics "
                "exposition. Vanilla HTML/JS/CSS, no framework, no build "
                "step. Read-only by default; the `Run` tab POSTs to "
                "/scenarios/{name}/run when invoked.\n\n"
                "The app.js / styles.css references are stamped with a "
                "`?v=<framework_version>` cache-buster so an upgrading "
                "browser always loads the matching JS/CSS instead of a "
                "stale cached copy."
            ),
            tags=["ui"],
            response_class=HTMLResponse,
        )
        def get_ui_root() -> HTMLResponse:
            index = _STATIC_DIR / "index.html"
            if not index.is_file():
                raise HTTPException(
                    status_code=500,
                    detail=f"static/index.html missing under {_STATIC_DIR}",
                )
            html = index.read_text(encoding="utf-8")
            # Cache-bust the static asset references on every version
            # bump. Without this, a browser that loaded a prior version
            # serves the cached app.js/styles.css and misses the new
            # behaviour (the exact failure mode that hid the 0.63.6
            # markdown-image renderer until a hard reload).
            html = html.replace(
                "/ui/static/styles.css",
                f"/ui/static/styles.css?v={__version__}",
            ).replace(
                "/ui/static/app.js",
                f"/ui/static/app.js?v={__version__}",
            )
            # The HTML carries the version stamp, so it must NEVER be
            # served stale — otherwise the browser keeps an old copy
            # that points at the old (cached) app.js and the stamp is
            # moot. Two-tier caching: this HTML is no-store; the
            # versioned static assets it references are cacheable
            # forever because their URL changes per release.
            return HTMLResponse(
                content=html,
                media_type="text/html; charset=utf-8",
                headers={"Cache-Control": "no-store, must-revalidate"},
            )

        @app.get(
            "/",
            summary="Redirect / → /ui for convenience",
            include_in_schema=False,
        )
        def root_redirect():
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url="/ui", status_code=302)

    # ------------------------------------------------------------------
    # Ophamin Console — the serious React GUI (Claude Design export).
    # Served alongside the provisional /ui SPA. React + Babel-standalone
    # in-browser (no build step). The Overview / Proofs / Scenarios / Run
    # / Telemetry screens live-wire to this server's REST endpoints via
    # data.js's hydrate(); the remaining screens render grounded mock.
    # ------------------------------------------------------------------

    if _CONSOLE_DIR.is_dir():
        app.mount(
            "/app/static",
            StaticFiles(directory=str(_CONSOLE_DIR)),
            name="ophamin-console-static",
        )

        @app.get(
            "/app",
            summary="Ophamin Console (React GUI)",
            description=(
                "Serves the React 'Ophamin Console' — the production GUI "
                "exported from Claude Design. React 18 + Babel-standalone "
                "compile in the browser; no build step, matching the "
                "framework's no-build philosophy.\n\n"
                "The bundle's relative `app/…` asset references are "
                "rewritten to absolute `/app/static/app/…` and stamped "
                "with a `?v=<framework_version>` cache-buster (same "
                "discipline as `/ui`). The HTML itself is served "
                "`no-store` so an upgrading browser never pairs new HTML "
                "with stale, cached JS.\n\n"
                "On boot, `data.js`'s `hydrate()` overlays the live REST "
                "surface (`/version`, `/scenarios`, `/proofs/bundles/tree` "
                "+ `/proofs/bundles/file`, `/metrics`) onto the grounded "
                "illustrative defaults — falling back to the mock per "
                "endpoint when a fetch fails (offline / fresh instance)."
            ),
            tags=["ui"],
            response_class=HTMLResponse,
        )
        def get_console_root() -> HTMLResponse:
            index = _CONSOLE_DIR / "index.html"
            if not index.is_file():
                raise HTTPException(
                    status_code=500,
                    detail=f"console/index.html missing under {_CONSOLE_DIR}",
                )
            html = index.read_text(encoding="utf-8")
            # Absolutize + cache-bust every bundle asset reference so the
            # page loads its JS/CSS/data from /app/static and an upgrade
            # never serves a stale mix.
            html = _CONSOLE_ASSET_RE.sub(
                lambda m: (
                    f'{m.group(1)}="/app/static/app/{m.group(2)}'
                    f'?v={__version__}"'
                ),
                html,
            )
            # Tell the bundle where its assets + REST surface live. The
            # force-load fallback in app.jsx reads OPHAMIN_ASSET_BASE; the
            # hydrate() in data.js reads OPHAMIN_API_BASE. Injected right
            # after <body> so it runs before any bundle script.
            inject = (
                "<script>"
                "window.OPHAMIN_ASSET_BASE='/app/static/app/';"
                "window.OPHAMIN_API_BASE='';"
                "</script>"
            )
            html = html.replace("<body>", "<body>\n" + inject, 1)
            return HTMLResponse(
                content=html,
                media_type="text/html; charset=utf-8",
                headers={"Cache-Control": "no-store, must-revalidate"},
            )

    # ------------------------------------------------------------------
    # Unified error envelope — any uncaught exception becomes a
    # JSON 500 with the type + message, NOT a raw stack trace.
    # ------------------------------------------------------------------

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={
                "detail": f"internal error: {type(exc).__name__}: {exc}",
                "framework_version": __version__,
            },
        )

    return app


__all__ = [
    "SERVER_NAME",
    "SERVER_TITLE",
    "SERVER_VERSION",
    "build_app",
    "VerifyRequest",
    "CanonicalizeRequest",
    "ProofIndexRequest",
    "RunScenarioRequest",
]
