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
)
from pydantic import BaseModel, Field

from ophamin import __version__
from ophamin.http_api.bundle_browser import (
    BundlePathError,
    bundle_tree,
    safe_bundle_file_path,
)
from ophamin.http_api.metrics import (
    http_metrics_middleware_factory,
    render_exposition,
)
from ophamin.interfaces._impls import (
    canonicalize_value_impl,
    get_scenario_claim_impl,
    list_agents_impl,
    authoring_capabilities_impl,
    config_effective_impl,
    config_schema_impl,
    config_validate_impl,
    list_cockpit_impl,
    management_status_impl,
    materialize_spec_impl,
    model_capabilities_impl,
    resolve_measurement_impl,
    toolkit_registry_impl,
    verify_grounding_impl,
    report_conformance_impl,
    report_standards_impl,
    list_flow_impl,
    list_integrations_impl,
    list_llm_calls_impl,
    list_scenarios_impl,
    list_substrate_impl,
    read_proof_index_impl,
    run_scenario_impl,
    validate_scenario_spec_impl,
    verify_proof_impl,
)

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


class ValidateSpecRequest(BaseModel):
    """Body of ``POST /authoring/validate``."""

    spec_json: str = Field(
        ...,
        description=(
            "The JSON text of a ScenarioSpec (a grounded experiment "
            "descriptor). Validated against the grounding gate: falsifiable "
            "threshold, scientific grounding, real (non-synthetic) data "
            "source, valid scope/facet/tools."
        ),
        examples=['{"title": "...", "scope": "flow", "threshold": {...}, ...}'],
    )


class ConfigValidateRequest(BaseModel):
    """Body of ``POST /configuring/validate``."""

    kimera_repo: str = Field(
        default="",
        description="Path to the Kimera repo (or set OPHAMIN_KIMERA_REPO).",
    )
    env_overrides: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Optional hypothetical environment to validate against (e.g. "
            "{'KIMERA_ENVIRONMENT': 'production'}) without changing the "
            "process env."
        ),
    )


class ReportConformanceRequest(BaseModel):
    """Body of ``POST /reporting/conformance``."""

    proof_json: str = Field(
        ...,
        description=(
            "The JSON text of a signed proof. Checked against the reporting "
            "gate: Ophamin naming conventions (content-hash proof_id, "
            "snake_case metric, verdict vocabulary, named evidence) + which "
            "recognised standards (in-toto / PROV-O / OSF / Croissant / HELM "
            "/ RO-Crate) the proof satisfies."
        ),
        examples=['{"proof_id": "...", "claim": {...}, "verdict": {...}}'],
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


class ChatRequest(BaseModel):
    """Body of ``POST /chat`` — one turn for the local-LLM advisory layer.

    An LLM is allowed HERE (Ophamin is the layer *about* Kimera): it only
    advises, never overrides ``Verdict.decide()``, and never runs inside
    Kimera's measurement path. The substrate itself contains no LLM.
    """

    question: str = Field(..., description="The user's natural-language question.")
    history: list[dict[str, str]] = Field(
        default_factory=list,
        description="Prior turns as [{role, content}] (role: 'user' | 'assistant').",
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

    @app.get(
        "/significance",
        summary="Plain-language meaning of a proof outcome",
        description=(
            "Return the authored, verdict-aware plain-language significance for a "
            "proof — 'what this means about Kimera' — keyed by the pre-registered "
            "metric. Same single source the static renderers use "
            "(ophamin.reporting.significance); no model in the loop. "
            "``significance`` is null when the metric has no authored meaning (an "
            "honest gap, never fabricated). Lets the console + any client render "
            "the same meaning a rendered proof carries."
        ),
        tags=["proofs"],
    )
    def get_significance(
        metric: str, outcome: str, observed: float | None = None
    ) -> dict[str, Any]:
        from ophamin.reporting.significance import plain_significance

        record = {
            "claim": {"threshold": {"metric": metric}},
            "verdict": {"outcome": outcome, "observed_value": observed},
        }
        return {
            "metric": metric,
            "outcome": outcome,
            "significance": plain_significance(record),
        }

    # ------------------------------------------------------------------
    # Agentic layer — read-only surfaces
    #
    # The agent layer is advisory + default-off + opt-in per call, and no
    # external LLM ever authors a verdict. These endpoints expose it
    # read-only: the agent catalogue, and the signed LLMCallRecord audit
    # trail. Neither runs an agent (agents are CLI-driven, by design).
    # ------------------------------------------------------------------

    @app.get(
        "/agents",
        summary="List the agentic-layer agents",
        description=(
            "Enumerate the seven advisory agents (prereg / scenario-gen "
            "/ adapt / brief / triage / confounds / query) with their "
            "model tier (sourced from `TASK_ROUTING`) and CLI command. "
            "Read-only — this does NOT run an agent. Agents are invoked "
            "via the `ophamin agent …` CLI; no external LLM ever touches "
            "a scenario's measurement path."
        ),
        tags=["agents"],
    )
    def get_agents() -> dict[str, Any]:
        return list_agents_impl()

    @app.get(
        "/agents/calls",
        summary="Signed LLM-call audit trail",
        description=(
            "Walk `<proofs_root>/llm_calls/` and return a newest-first "
            "summary of every agent invocation's content-addressed, "
            "HMAC-signed `LLMCallRecord` — task / runtime / model / "
            "tokens / latency / signature prefix + a `verified` flag from "
            "re-checking the HMAC. Prompt messages + response content are "
            "NOT included (audit metadata only). Returns an empty list "
            "when no agent has been run yet."
        ),
        tags=["agents"],
    )
    def get_agent_calls(
        proofs_root: str = "proofs", limit: int = 200,
    ) -> dict[str, Any]:
        return list_llm_calls_impl(proofs_root, limit)

    @app.get(
        "/integrations",
        summary="External tools the operator has wired up",
        description=(
            "Ophamin wraps mature OSS (MLflow, Grafana, DVC, SARIF "
            "viewers, the docs site) — each with its own UI. Rather than "
            "re-skin them, the Console routes to them. This returns which "
            "tools are configured (via env vars such as "
            "`OPHAMIN_GRAFANA_URL`; MLflow also honours "
            "`MLFLOW_TRACKING_URI`) and what each replaces. Bring-your-own: "
            "nothing is configured by default."
        ),
        tags=["integrations"],
    )
    def get_integrations() -> dict[str, Any]:
        return list_integrations_impl()

    @app.get(
        "/substrate",
        summary="Substrate-organ state from the signed proof corpus",
        description=(
            "Observes the substrate-under-test (Kimera) through what the "
            "signed proofs measured about it. Groups the latest proof per "
            "scenario into named substrate organs — GWF (immune), Walker "
            "(traversal), prime apparatus, scar/vault memory, Φ "
            "(integration), dissonance, Rosetta (language), interface "
            "contract — each with its headline metric + verdict. Real + "
            "signed + always available (no live Kimera required). A live "
            "`KimeraAdapter` probe is a separate opt-in path."
        ),
        tags=["substrate"],
    )
    def get_substrate(proofs_root: str = "proofs") -> dict[str, Any]:
        return list_substrate_impl(proofs_root)

    @app.get(
        "/cockpit",
        summary="Engineering-facet health, tracked over substrate commits",
        description=(
            "The Build Cockpit: the `engineering` facet of the protocol. "
            "Aggregates the engineering checks (architectural completeness "
            "/ orphan rate, interface contract, code quality, throughput, "
            "reproducibility) from the signed proof corpus into a "
            "per-substrate-commit timeline, so the trend is visible as "
            "Kimera is built. Read-only; checks with no proof yet surface "
            "as `no_data`."
        ),
        tags=["cockpit"],
    )
    def get_cockpit(proofs_root: str = "proofs") -> dict[str, Any]:
        return list_cockpit_impl(proofs_root)

    @app.get(
        "/flow",
        summary="Flow-scope proofs (properties over a trajectory)",
        description=(
            "The `flow` scope of the protocol: proofs of a temporal-logic "
            "invariant checked across a whole trajectory of cycles, not at "
            "a single point — e.g. memory-as-deformation recognition "
            "stability under re-exposure. Returns each flow proof's "
            "recognition trajectory (floor, mean, per-stimulus floors, the "
            "worst pair, the full per-pair series) so the dynamics are "
            "visible, not just the verdict. Read-only + signed."
        ),
        tags=["flow"],
    )
    def get_flow(proofs_root: str = "proofs") -> dict[str, Any]:
        return list_flow_impl(proofs_root)

    @app.get(
        "/authoring/capabilities",
        summary="The live menu of real resources an experiment can be built on",
        description=(
            "What a (human or model) author may select from when describing "
            "an experiment: the corpora actually registered on this install, "
            "the Protocol scopes + facets, the invariant templates that map "
            "to runnable scenarios, the measurement tools/pillars, and the "
            "recognised scientific standards. Sourced from the live "
            "registries — never a drift-prone hand-maintained list. "
            "Deterministic; no LLM."
        ),
        tags=["authoring"],
    )
    def get_authoring_capabilities() -> dict[str, Any]:
        return authoring_capabilities_impl()

    @app.post(
        "/authoring/validate",
        summary="Validate a scenario spec against the grounding gate",
        description=(
            "Checks a ScenarioSpec so an ungrounded or synthetic experiment "
            "fails before it can become a scenario, no matter who wrote it. "
            "Requires: a falsifiable threshold, >=1 scientific grounding "
            "(paper/standard), a real registered data source (never "
            "synthetic/inline/mock), valid scope/facet, and tools/templates "
            "that actually exist. Returns `acceptable` + a structured "
            "violation punch list. Never raises."
        ),
        tags=["authoring"],
    )
    def post_validate_spec(body: ValidateSpecRequest) -> dict[str, Any]:
        return validate_scenario_spec_impl(body.spec_json)

    @app.post(
        "/authoring/materialize",
        summary="Dry-run: validate a spec + describe the scenario it would build",
        description=(
            "Closes the design loop: validates a ScenarioSpec against the "
            "grounding gate and, if it passes, describes the exact runnable "
            "scenario it materialises into (class, scope, facet, metric, "
            "threshold, data source, cycle count) — WITHOUT running it "
            "(execution needs a live substrate + minutes). A non-conformant "
            "spec returns the violation punch list. Never raises."
        ),
        tags=["authoring"],
    )
    def post_materialize_spec(body: ValidateSpecRequest) -> dict[str, Any]:
        return materialize_spec_impl(body.spec_json)

    @app.post(
        "/authoring/verify-grounding",
        summary="Verify a spec's citations resolve to real, readable papers",
        description=(
            "Turns grounding from a formality into enforcement. Each citation "
            "is resolved by direct link (arXiv API / Crossref DOI / URL) or "
            "against the local papers directory (OPHAMIN_PAPERS_DIR) — reading "
            "the paper to recover its real title. A fabricated citation "
            "(`unresolved`) fails verification; network errors (`unreachable`) "
            "are reported but tolerated for offline use. Local citations are "
            "always checkable offline. Never raises."
        ),
        tags=["authoring"],
    )
    def post_verify_grounding(body: ValidateSpecRequest) -> dict[str, Any]:
        return verify_grounding_impl(body.spec_json)

    @app.get(
        "/models",
        summary="Configured agentic models — tiers, dedicated specialties, providers",
        description=(
            "The model routing the agentic system uses for analysis / "
            "diagnosis / authoring: the general tiers (fast / workhorse / "
            "coder / reasoning) plus the **dedicated** scientific + "
            "engineering tiers, each with its model, provider (local-first; "
            "external API opt-in per tier), and the env-var name a key is "
            "read from (never the key itself). Also the per-task → tier map. "
            "These models never run in the measurement path — tooling layer "
            "only, per the no-external-LLM rule."
        ),
        tags=["models"],
    )
    def get_models(check_availability: bool = False) -> dict[str, Any]:
        # ?check_availability=true probes each runtime's /v1/models so the
        # surface can show whether a configured (dedicated) model is actually
        # installed — best-effort network I/O, off by default.
        return model_capabilities_impl(check_availability=check_availability)

    @app.get(
        "/toolkits",
        summary="Unified toolkit index — route to every wrapped tool's native interface",
        description=(
            "Every external open-source toolkit Ophamin builds on: its role, "
            "installed version, and a direct link to its NATIVE interface "
            "(docs, and a live UI where one exists — MLflow / DVC / "
            "Prometheus). Ophamin routes to each tool's own interface rather "
            "than hiding it. Extensible via the OPHAMIN_TOOLKITS env var "
            "(a JSON list of custom toolkits)."
        ),
        tags=["toolkits"],
    )
    def get_toolkits() -> dict[str, Any]:
        return toolkit_registry_impl()

    @app.get(
        "/authoring/resolve-measurement",
        summary="Route a missing-measurement need across compose / wire / synthesize",
        description=(
            "Given a stated measurement requirement (e.g. one a finished "
            "experiment surfaced), assemble ranked candidates from the three "
            "lists — the capability menu (compose), the toolkit registry "
            "(wire), and recognised standards (ground) — with a heuristic "
            "recommended path. The agent makes the final selection; the "
            "grounding gate refuses an invented, ungrounded metric."
        ),
        tags=["authoring"],
    )
    def get_resolve_measurement(need: str) -> dict[str, Any]:
        return resolve_measurement_impl(need)

    @app.get(
        "/reporting/standards",
        summary="Recognised report standards + output formats + naming conventions",
        description=(
            "The reporting menu: which scientific/industrial standards a "
            "report can declare conformance to (in-toto/DSSE, W3C PROV-O, "
            "OSF Registered Reports, MLCommons Croissant, Stanford HELM, "
            "RO-Crate), the output formats the wheel renders, the verdict "
            "vocabulary, and the canonical bundle-name + metric naming "
            "conventions. Deterministic; read-only."
        ),
        tags=["reporting"],
    )
    def get_reporting_standards() -> dict[str, Any]:
        return report_standards_impl()

    @app.post(
        "/reporting/conformance",
        summary="Check a proof's nomenclature + standards coverage (the reporting gate)",
        description=(
            "The output analog of the authoring grounding gate. Checks a "
            "signed proof against Ophamin's naming conventions (content-hash "
            "proof_id, snake_case metric, fixed verdict vocabulary, named "
            "evidence, derivable bundle name) and reports which recognised "
            "standards it satisfies. Returns `conformant` + an actionable "
            "punch list. Never raises."
        ),
        tags=["reporting"],
    )
    def post_reporting_conformance(body: ReportConformanceRequest) -> dict[str, Any]:
        return report_conformance_impl(body.proof_json)

    @app.get(
        "/configuring/schema",
        summary="Kimera's env-var config knob contract (introspected from source)",
        description=(
            "Ophamin's Configure facet: the live set of Kimera configuration "
            "knobs — app-level (database / api / system) and the "
            "substrate-tuning domain knobs (geoid / scar / thermodynamic / "
            "ecoform / operator / event-matching) — each with its env var, "
            "default, inferred type, group, source file, and secret flag. "
            "Parsed statically from Kimera's source (no import, no run). "
            "Pass ?kimera_repo=… or set OPHAMIN_KIMERA_REPO."
        ),
        tags=["configuring"],
    )
    def get_config_schema(kimera_repo: str = "") -> dict[str, Any]:
        return config_schema_impl(kimera_repo)

    @app.get(
        "/configuring/effective",
        summary="The effective Kimera config + a provenance snapshot",
        description=(
            "Each knob resolved to its current value (env override or "
            "default), secrets redacted, plus a secret-safe content-hashed "
            "snapshot that can tie a proof to the exact config that produced "
            "it. Read-only."
        ),
        tags=["configuring"],
    )
    def get_config_effective(kimera_repo: str = "") -> dict[str, Any]:
        return config_effective_impl(kimera_repo)

    @app.post(
        "/configuring/validate",
        summary="Validate Kimera's config against the config gate",
        description=(
            "The config gate: every knob value must parse as its type, and a "
            "config declared `production` must not ship dev-only / unsafe "
            "settings (empty DB password, debug on, reload on, bind-all "
            "host). `env_overrides` lets you test a hypothetical environment. "
            "Returns `valid` + an actionable violation list. Never raises."
        ),
        tags=["configuring"],
    )
    def post_config_validate(body: ConfigValidateRequest) -> dict[str, Any]:
        return config_validate_impl(body.kimera_repo, body.env_overrides)

    @app.get(
        "/managing/status",
        summary="Live Kimera substrate status / health (the Manage facet)",
        description=(
            "Ophamin's Manage facet — the Control room's live backend. Probes "
            "the connected Kimera substrate (real adapter probe) and reports "
            "its commit, runner readiness, and per-cognitive-surface import "
            "health (entity / arachne / walker / gwf / piovra / rosetta / "
            "ouroboros / pentecost / astrolabe / atlas / spde …). A missing or "
            "un-runnable substrate is reported as `ready: false` with the "
            "error, never a crash. Pass ?kimera_repo=… or set "
            "OPHAMIN_KIMERA_REPO. Note: probing imports Kimera in a "
            "subprocess, so this call can take several seconds."
        ),
        tags=["managing"],
    )
    def get_managing_status(kimera_repo: str = "", target: str = "entity") -> dict[str, Any]:
        return management_status_impl(kimera_repo, target)

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
    # Advisory chat — Ophamin's local LLM (NEVER Kimera's substrate)
    # ------------------------------------------------------------------

    @app.post(
        "/chat",
        summary="Ask Ophamin's local-LLM advisory layer (never the substrate)",
        description=(
            "Route a natural-language question to Ophamin's local LLM "
            "(OpenAI-compatible runtime at OPHAMIN_LLM_BASE_URL — Ollama / "
            "LM Studio / MLX-LM). An LLM is allowed HERE because Ophamin is the "
            "layer *about* Kimera: it only advises, never overrides "
            "verdict.decide(), and never runs inside Kimera's measurement path "
            "(the substrate itself contains no LLM). Gated on a reachable local "
            "LLM serving a real model — returns 503 when none is running, so the "
            "console falls back to an honest 'not wired' state rather than "
            "fabricate a reply. Picks a model actually present on the runtime "
            "(no silent default to an absent one). Chat turns are ephemeral "
            "advisory and are NOT persisted as signed records; the agent tasks "
            "that produce durable artifacts do persist. NOTE: this exposes LLM "
            "inference over HTTP — fine on a local console; gate/auth it before "
            "a shared deployment."
        ),
        responses={
            400: {"description": "Empty question"},
            502: {"description": "The LLM runtime errored mid-generation"},
            503: {"description": "No local LLM reachable (set OPHAMIN_LLM_BASE_URL + run a model)"},
        },
        tags=["chat"],
    )
    def chat(body: ChatRequest) -> dict[str, Any]:
        import os as _os

        from ophamin.agentic import LLMClient, LLMClientError
        from ophamin.agentic.models import DEFAULT_TIER_MODELS, TaskTier

        question = (body.question or "").strip()
        if not question:
            raise HTTPException(status_code=400, detail="empty question")

        client = LLMClient()
        # Probe what the runtime actually serves; never default to a model that
        # isn't installed (a 404 surprise) — and 503 honestly if nothing is up.
        try:
            available = client.list_models()
        except LLMClientError as exc:
            raise HTTPException(
                status_code=503,
                detail=(
                    f"No local LLM reachable at {client.base_url} "
                    f"({client.runtime_hint}). Start one (e.g. `ollama serve` + "
                    f"`ollama pull llama3.1:8b`) or set OPHAMIN_LLM_BASE_URL. {exc}"
                ),
            ) from exc
        if not available:
            raise HTTPException(
                status_code=503,
                detail=f"Local LLM at {client.base_url} serves no models.",
            )

        def _present(tag: str) -> bool:
            return tag in available or any(
                m == tag or m.split(":")[0] == tag.split(":")[0] for m in available
            )

        preferred = _os.environ.get("OPHAMIN_LLM_MODEL_CHAT", "").strip()
        fast = DEFAULT_TIER_MODELS[TaskTier.FAST]
        model = (
            preferred if (preferred and _present(preferred))
            else fast if _present(fast)
            else available[0]
        )

        system = (
            "You are Ophamin's assistant — the observatory layer that makes "
            "Kimera-SWM legible. Ground EVERY answer in the facts below and do "
            "not contradict or embellish them:\n"
            "- SWM = Spherical Word Memory. Kimera's memory IS a spherical "
            "manifold; a concept is a point on it; experience permanently "
            "deforms it (a 'scar'); recall follows the deformed topology.\n"
            "- Kimera-SWM is an attempt to create a cybernetic, physics-based "
            "intelligence — NOT a language model, NOT human cognition. Its "
            "substrate operates on primes (native energy scale E_p = log p), "
            "geoids, scars, a Walker that resolves contradictions, and Piovra "
            "sensory arms. The substrate causes its own intelligence and "
            "contains NO LLM of any kind.\n"
            "- Ophamin is the observatory around Kimera: it measures the "
            "substrate and emits signed, content-addressed, falsifiable proofs "
            "(verdicts VALIDATED / REFUTED / INCONCLUSIVE).\n"
            "You only ADVISE: you never decide a verdict, and you are not part "
            "of Kimera's substrate. If you do not know a specific (a number, a "
            "proof, an acronym's expansion), SAY you do not know and point to "
            "the Proofs / Agents / Roadmap screens — NEVER guess or invent. "
            "Admitting a gap is always better than a plausible-sounding "
            "falsehood."
        )
        # Ground the reply in the real proof corpus (RAG): retrieve the most
        # relevant scenarios / verdicts / significance and hand them to the model
        # as context, so it cites real proofs — not its training data. Best-effort:
        # empty when nothing matches; the model then leans on its seeded facts.
        from ophamin.http_api.chat_grounding import ground
        grounded = ground(question)

        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        if grounded:
            messages.append({
                "role": "system",
                "content": (
                    "Relevant REAL records from Ophamin's signed-proof corpus, "
                    "below. Answer the user by SYNTHESISING from them — the goal, "
                    "claim, threshold, latest verdict, observed value, and "
                    "what-it-means are all real and citable. Only say you don't "
                    "have something when these records genuinely lack it; never "
                    "invent a number or verdict beyond them:\n"
                    + grounded
                ),
            })
        for turn in body.history[-8:]:
            role = turn.get("role")
            content = turn.get("content")
            if role in ("user", "assistant") and isinstance(content, str):
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": question})

        try:
            resp = client.chat(
                model=model, messages=messages, max_tokens=1024, temperature=0.3,
            )
        except LLMClientError as exc:
            raise HTTPException(
                status_code=502, detail=f"LLM runtime error: {exc}",
            ) from exc

        return {
            "reply": resp.content,
            "reasoning": resp.reasoning or None,
            "model": resp.model,
            "runtime": client.runtime_hint,
            "latency_ms": round(resp.latency_ms, 1),
            "completion_tokens": resp.completion_tokens,
        }

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

        def _render_home() -> HTMLResponse:
            # The spherical home — Kimera at the centre, six wheels around it
            # (Ophanim = wheels within wheels). The shape IS the navigation:
            # built for a visual / analogy thinker rather than a dashboard
            # grid. Same cache-bust + no-store discipline as /ui.
            home = _STATIC_DIR / "home.html"
            if not home.is_file():
                raise HTTPException(
                    status_code=500,
                    detail=f"static/home.html missing under {_STATIC_DIR}",
                )
            html = home.read_text(encoding="utf-8")
            html = html.replace(
                "/ui/static/home.css",
                f"/ui/static/home.css?v={__version__}",
            ).replace(
                "/ui/static/home.js",
                f"/ui/static/home.js?v={__version__}",
            )
            return HTMLResponse(
                content=html,
                media_type="text/html; charset=utf-8",
                headers={"Cache-Control": "no-store, must-revalidate"},
            )

        @app.get(
            "/",
            summary="The spherical home — Kimera + six wheels (front door)",
            include_in_schema=False,
            response_class=HTMLResponse,
        )
        def get_home_root() -> HTMLResponse:
            return _render_home()

        @app.get(
            "/home",
            summary="The spherical home — Kimera at the centre, six wheels around it",
            description=(
                "Ophamin's front door, served as the navigable structure "
                "itself: the Kimera substrate at the centre with the six "
                "observatory wheels (seeing · measuring · comparing · "
                "instrumenting · auditing · reporting) around it. Click a "
                "wheel to enter it. Vanilla HTML/SVG/JS, no build step; "
                "every panel live-wires to this server's real REST surface "
                "(no fabricated data). The classic surfaces remain at /app "
                "(React console) and /ui (provisional SPA)."
            ),
            tags=["ui"],
            response_class=HTMLResponse,
        )
        def get_home() -> HTMLResponse:
            return _render_home()

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
            def _asset_buster(m: "re.Match[str]") -> str:
                asset = m.group(2)
                # Bust on content change, not just release: append the asset's
                # mtime, so an edited .jsx/.css/.js is re-fetched even within a
                # version. The HTML is no-store; without this, a returning
                # browser pins stale console JS until the version bumps — which
                # makes iterating on the GUI invisible to anyone who has visited.
                ver = __version__
                try:
                    mtime = int((_CONSOLE_DIR / "app" / asset).stat().st_mtime)
                    ver = f"{__version__}-{mtime}"
                except OSError:
                    pass
                return f'{m.group(1)}="/app/static/app/{asset}?v={ver}"'

            html = _CONSOLE_ASSET_RE.sub(_asset_buster, html)
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
