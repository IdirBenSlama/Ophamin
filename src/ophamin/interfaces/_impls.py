"""Pure transport-agnostic tool implementations.

The MCP server (:mod:`ophamin.mcp`) and the HTTP REST API
(:mod:`ophamin.http_api`) both wrap these functions verbatim.
Changing behaviour means changing this module.

Each function takes JSON-friendly string arguments and returns a
JSON-friendly ``dict[str, Any]``. The sign-key argument
``sign_key_b64`` is base64-encoded bytes; an empty string is the
framework-wide ``DEFAULT_SIGN_KEY``.

Functions:

- :func:`list_scenarios_impl`
- :func:`get_scenario_claim_impl`
- :func:`verify_proof_impl`
- :func:`canonicalize_value_impl`
- :func:`read_proof_index_impl`
- :func:`run_scenario_impl`
- :func:`scenario_metadata` (internal helper)
- :func:`decode_sign_key` (internal helper)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from pathlib import Path
from typing import Any

from opentelemetry.trace import Status, StatusCode

from ophamin import __version__
from ophamin.measuring.proof.codec import iter_proofs, load
from ophamin.measuring.proof.record import _canonical, content_hash
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, SCENARIOS, Tier
from ophamin.observability.otel import OphaminInstrumentor
from ophamin.seeing.substrate.mock import MockSubstrate


# --------------------------------------------------------------------------
# Helper: decode an optional base64-encoded signing key argument
# --------------------------------------------------------------------------


def decode_sign_key(sign_key_b64: str) -> bytes:
    """Return the bytes of a signing key, either from base64 or the default.

    Transport-agnostic: every interface (MCP / HTTP / ...) accepts the
    signing key as a base64-encoded string so it round-trips cleanly
    through JSON. Empty string → use Ophamin's framework-wide
    ``DEFAULT_SIGN_KEY``.

    Raises:
        ValueError: if the input is non-empty but not valid base64.
    """
    if not sign_key_b64:
        return DEFAULT_SIGN_KEY
    try:
        return base64.b64decode(sign_key_b64, validate=True)
    except Exception as exc:  # narrow: base64 raises binascii.Error
        raise ValueError(
            f"sign_key_b64 must be valid standard base64 (got {len(sign_key_b64)} "
            f"chars); base64 decode failed: {exc}"
        ) from exc


def scenario_metadata(name: str) -> dict[str, Any]:
    """Read-only metadata for a single scenario class.

    Raises:
        ValueError: if ``name`` isn't in :data:`SCENARIOS`.
    """
    if name not in SCENARIOS:
        raise ValueError(
            f"unknown scenario {name!r}; available scenarios via list_scenarios"
        )
    cls = SCENARIOS[name]
    tier = getattr(cls, "tier", None)
    tier_label = tier.value if isinstance(tier, Tier) else str(tier)
    return {
        "name": name,
        "family": getattr(cls, "family", ""),
        "tier": tier_label,
        "target": getattr(cls, "target", ""),
        "goal": getattr(cls, "goal", ""),
        "method": getattr(cls, "method", ""),
        "corpus_name": getattr(cls, "corpus_name", ""),
        "falsification_consequence": getattr(cls, "falsification_consequence", ""),
        "explanation": getattr(cls, "explanation", ""),
    }


# --------------------------------------------------------------------------
# Tool implementations
# --------------------------------------------------------------------------


def list_scenarios_impl() -> dict[str, Any]:
    """Enumerate every scenario in the registry with metadata."""
    scenarios = [scenario_metadata(name) for name in sorted(SCENARIOS)]
    return {
        "count": len(scenarios),
        "scenarios": scenarios,
        "framework_version": __version__,
    }


# --------------------------------------------------------------------------
# Agentic layer — read-only surfaces.
#
# The agent layer is advisory + default-off + opt-in per call, and never
# inside a scenario's measurement path (no external LLM ever authors a
# verdict). These two impls expose it *read-only* over HTTP/MCP: the
# catalogue of agents, and the signed `LLMCallRecord` audit trail that
# every agent invocation persists. Neither runs an agent.
# --------------------------------------------------------------------------

#: The seven agents, by CLI subcommand. ``task`` is the internal routing
#: key in :data:`ophamin.agentic.models.TASK_ROUTING` (which is the
#: authoritative source for each agent's model *tier*).
_AGENT_CATALOG: tuple[tuple[str, str, str, str], ...] = (
    ("prereg", "prereg_validator", "Prereg validator",
     "Flags whether a claim is actually falsifiable before a run."),
    ("scenario-gen", "scenario_gen", "Scenario generator",
     "Scaffolds a Scenario subclass from a claim (leaves score() a stub)."),
    ("adapt", "adapter_gen", "Adapter generator",
     "Generates a Foreign-Corpus adapter module."),
    ("brief", "proof_brief", "Proof brief",
     "Plain-English brief for a signed proof."),
    ("triage", "refuted_triage", "Refuted triage",
     "Proposes follow-up scenarios for a REFUTED proof."),
    ("confounds", "confound_enumerator", "Confound enumerator",
     "Red-teams a VALIDATED proof — surfaces alternative explanations."),
    ("query", "bundle_query", "Bundle query",
     "Natural-language query over the proof-bundle tree."),
)


def list_agents_impl() -> dict[str, Any]:
    """Enumerate the seven agentic-layer agents with their model tier.

    Read-only. The tier per agent is sourced from
    :data:`ophamin.agentic.models.TASK_ROUTING` so this never duplicates
    the routing table — it reflects it. Importing from the dep-light
    ``models`` module avoids pulling the LLM-client extras.
    """
    from ophamin.agentic.models import TASK_ROUTING

    agents: list[dict[str, Any]] = []
    for cli_id, task, label, desc in _AGENT_CATALOG:
        tier = TASK_ROUTING.get(task)
        agents.append({
            "id": cli_id,
            "task": task,
            "label": label,
            "desc": desc,
            "tier": tier.value if tier is not None else "",
            "cli": f"ophamin agent {cli_id}",
        })
    return {
        "count": len(agents),
        "agents": agents,
        "framework_version": __version__,
    }


def list_llm_calls_impl(
    proofs_root: str | Path = "proofs",
    limit: int = 200,
) -> dict[str, Any]:
    """Walk ``<proofs_root>/llm_calls/`` and return signed-call summaries.

    Each agent invocation persists a content-addressed, HMAC-signed
    ``LLMCallRecord`` under ``llm_calls/<YYYY-MM-DD>/<short-id>.json``.
    This returns a newest-first summary of each (no prompt ``messages``
    or response ``content`` — just the audit metadata) plus a ``verified``
    flag from re-checking the HMAC against the default audit key.

    Read-only + best-effort: a record that fails to parse is skipped (the
    enumeration must not 500 on one malformed file). Returns an empty
    list when no calls have been recorded yet — not an error.
    """
    from ophamin.agentic.audit import DEFAULT_LLM_AUDIT_KEY, LLMCallRecord

    root = Path(proofs_root) / "llm_calls"
    calls: list[dict[str, Any]] = []
    if not root.is_dir():
        return {"count": 0, "calls": [], "framework_version": __version__}

    for date_dir in sorted(root.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue
        for f in sorted(date_dir.glob("*.json"), reverse=True):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            req = d.get("request", {}) or {}
            resp = d.get("response", {}) or {}
            verified = False
            try:
                rec = LLMCallRecord(
                    task=d.get("task", ""),
                    runtime=d.get("runtime", ""),
                    model=req.get("model", ""),
                    messages=req.get("messages", []),
                    max_tokens=req.get("max_tokens", 0),
                    temperature=req.get("temperature", 0.0),
                    response_format=req.get("response_format", ""),
                    content=resp.get("content", ""),
                    finish_reason=resp.get("finish_reason", ""),
                    prompt_tokens=resp.get("prompt_tokens", 0),
                    completion_tokens=resp.get("completion_tokens", 0),
                    latency_ms=resp.get("latency_ms", 0.0),
                    ophamin_version=(d.get("identity", {}) or {}).get(
                        "ophamin_version", ""
                    ),
                    created_at=d.get("created_at", ""),
                    signature=d.get("signature", ""),
                )
                verified = rec.verify_signature(DEFAULT_LLM_AUDIT_KEY)
            except (TypeError, KeyError, ValueError):
                verified = False
            calls.append({
                "call_id": d.get("call_id", ""),
                "task": d.get("task", ""),
                "runtime": d.get("runtime", ""),
                "model": req.get("model", ""),
                "created_at": d.get("created_at", ""),
                "latency_ms": resp.get("latency_ms"),
                "prompt_tokens": resp.get("prompt_tokens"),
                "completion_tokens": resp.get("completion_tokens"),
                "finish_reason": resp.get("finish_reason", ""),
                "signature_prefix": (d.get("signature", "") or "")[:16],
                "verified": verified,
                "date": date_dir.name,
            })
            if len(calls) >= limit:
                return {
                    "count": len(calls),
                    "calls": calls,
                    "framework_version": __version__,
                }
    return {
        "count": len(calls),
        "calls": calls,
        "framework_version": __version__,
    }


# --------------------------------------------------------------------------
# Integrations — the "route, don't reinvent" surface.
#
# Ophamin wraps mature OSS, each with its own battle-tested UI. Rather than
# re-skin Grafana / MLflow / DVC / SARIF viewers / the docs site, the
# Console routes to them. This impl reports which external tools the
# operator has wired up (via env vars). Bring-your-own: nothing is
# configured by default, and that's the honest state.
# --------------------------------------------------------------------------

#: Each integration: (id, name, env_vars [first set wins], replaces, description).
_INTEGRATIONS_CATALOG: tuple[tuple[str, str, tuple[str, ...], str, str], ...] = (
    ("grafana", "Grafana", ("OPHAMIN_GRAFANA_URL",),
     "Telemetry / drift dashboards",
     "Scrapes Ophamin's /metrics (Prometheus exposition); the canonical "
     "metrics + streaming-drift UI."),
    ("mlflow", "MLflow", ("OPHAMIN_MLFLOW_URL", "MLFLOW_TRACKING_URI"),
     "Run tracking / comparison",
     "Experiment-tracking UI — runs, params, metrics, artifacts, registry."),
    ("dvc", "DVC Studio", ("OPHAMIN_DVC_URL",),
     "Data lineage",
     "Data versioning + pipeline DAG (dvc dag / DVC Studio)."),
    ("provenance", "Provenance viewer", ("OPHAMIN_PROV_URL",),
     "Lineage graph",
     "PROV-O graph viewer for each proof's provenance section."),
    ("code_scanning", "Code scanning (SARIF)", ("OPHAMIN_SARIF_URL",),
     "Static-analysis audit",
     "SARIF viewer / code-scanning for the audit wheel's ruff/bandit/mypy "
     "output."),
    ("docs", "Documentation", ("OPHAMIN_DOCS_URL",),
     "Roadmap / governance",
     "The mkdocs documentation site (roadmap, governance, reference)."),
)


def list_integrations_impl() -> dict[str, Any]:
    """Report which external tools the operator has wired up.

    Read-only. Each integration is configured by an env var (e.g.
    ``OPHAMIN_GRAFANA_URL``); MLflow also honours its canonical
    ``MLFLOW_TRACKING_URI``. Nothing is configured by default — the
    Console shows a "how to wire this" card in that case rather than a
    re-implementation of the tool.
    """
    import os

    items: list[dict[str, Any]] = []
    for iid, name, env_vars, replaces, desc in _INTEGRATIONS_CATALOG:
        url = ""
        src_env = ""
        for ev in env_vars:
            v = os.environ.get(ev, "").strip()
            if v:
                url, src_env = v, ev
                break
        items.append({
            "id": iid,
            "name": name,
            "configured": bool(url),
            "url": url,
            "env_var": env_vars[0],
            "env_var_source": src_env,
            "replaces": replaces,
            "description": desc,
        })
    return {
        "count": len(items),
        "configured_count": sum(1 for i in items if i["configured"]),
        "integrations": items,
        "framework_version": __version__,
    }


# --------------------------------------------------------------------------
# Substrate — organ state from the SIGNED proof corpus.
#
# The substrate-under-test (Kimera) is observed through what the signed
# proofs measured about it. Rather than require a live Kimera (heavy +
# deployment-specific via the KimeraAdapter subprocess), this aggregates
# the latest signed proof per scenario into named substrate organs —
# real, signed, always available. A live adapter probe is a separate
# opt-in path (Phase 3c).
# --------------------------------------------------------------------------

#: Substrate organs keyed by the scenario *family* (authoritative from
#: the registry) — so the mapping adapts to whatever scenarios the corpus
#: actually contains rather than hardcoding scenario names. Families not
#: listed here (cross_framework, crdt, mutual_information, causal,
#: code_quality, reproducibility) are Ophamin's measurement-validation
#: tier, not Kimera substrate organs, and are excluded from this view.
_ORGAN_FAMILIES: dict[str, tuple[str, str]] = {
    "immune": ("GWF · immune membrane", "Blocks adversarial / manipulative input."),
    "walker": ("Walker · traversal", "Traverses the manifold to resolve contradictions."),
    "topology": ("Manifold topology", "Connectivity (β₀/β₁/β₂) of the geoid manifold."),
    "prime": ("Prime apparatus", "Content-addressed meaning — the substrate's vocabulary."),
    "quantum": ("Quantum basis", "Quantum-style prime state composition."),
    "memory": ("Scar / Vault · memory", "Experience deforms the manifold."),
    "phi": ("Φ · integration", "Integrated information over the substrate."),
    "dissonance": ("Dissonance", "Senses contradiction on cleared input."),
    "rosetta": ("Rosetta · language", "Cross-lingual canonicalization to one prime."),
    "conservation": ("Sinew · conservation", "Conserved quantities of substrate dynamics."),
    "self_discovery": ("Proprioception", "The substrate models its own state."),
    "self_reference": ("Self-reference", "Self-referential / recursive cognition."),
    "completeness": ("Completeness", "No hidden dead code at canonical names."),
    "interface": ("Interface contract", "Self-interface integrity."),
    "throughput": ("Throughput · cost", "Per-cycle wall-time + resource envelope."),
}


def list_substrate_impl(proofs_root: str | Path = "proofs") -> dict[str, Any]:
    """Aggregate substrate-organ state from the signed proof corpus.

    Groups the latest signed proof per scenario into named substrate
    organs (GWF / Walker / prime apparatus / scar-vault memory / Φ /
    dissonance / Rosetta / interface contract). Read-only + best-effort:
    a malformed record is skipped. Returns ``no_data`` organs (not an
    error) when the corpus hasn't exercised that organ yet.
    """
    from ophamin.measuring.proof.codec import iter_proofs

    # Authoritative scenario -> family map from the registry.
    scen_family = {name: getattr(SCENARIOS[name], "family", "") for name in SCENARIOS}

    latest: dict[str, dict[str, Any]] = {}
    scanned = 0
    root = Path(proofs_root)
    if root.is_dir():
        for p in iter_proofs(root):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            scanned += 1
            scenario = p.parent.parent.name
            v = d.get("verdict", {}) or {}
            thr = v.get("threshold", {}) or {}
            data = d.get("data", {}) or {}
            created = (d.get("identity", {}) or {}).get("created_at", "")
            prev = latest.get(scenario)
            if prev and str(prev.get("created_at", "")) >= str(created):
                continue
            latest[scenario] = {
                "scenario": scenario,
                "family": scen_family.get(scenario, ""),
                "outcome": v.get("outcome", ""),
                "observed": v.get("observed_value"),
                "metric": thr.get("metric", ""),
                "comparator": thr.get("comparator", ""),
                "threshold": thr.get("value"),
                "created_at": created,
                "substrate_name": data.get("substrate_name", ""),
                "substrate_commit": str(data.get("substrate_git_commit", ""))[:12],
            }

    organs: list[dict[str, Any]] = []
    for fam, (name, role) in _ORGAN_FAMILIES.items():
        found = [s for s in latest.values() if s.get("family") == fam]
        found.sort(key=lambda x: str(x.get("created_at", "")), reverse=True)
        head = found[0] if found else None
        outcome = (head or {}).get("outcome", "")
        organs.append({
            "id": fam,
            "name": name,
            "role": role,
            "scenarios": sorted(s["scenario"] for s in found),
            "proof_count": len(found),
            "latest": head,
            "status": (
                "validated" if outcome == "VALIDATED"
                else "refuted" if outcome == "REFUTED"
                else "inconclusive" if head
                else "no_data"
            ),
        })
    return {
        "count": len(organs),
        "organs": organs,
        "proofs_scanned": scanned,
        "framework_version": __version__,
    }


# --------------------------------------------------------------------------
# Build Cockpit — engineering-facet health of the substrate-under-test,
# tracked OVER substrate commits (the trend Kimera's development needs).
#
# Protocol facet: `engineering`. Same signed-corpus source as /substrate,
# but where /substrate shows the latest organ state, the cockpit shows the
# per-commit TIMELINE for each engineering check — so the operator (and
# their code model) can see whether Kimera is getting healthier or worse
# as it's built. Real + signed + always available.
# --------------------------------------------------------------------------

#: The engineering-facet checks, keyed by the scenario family.
_COCKPIT_CHECKS: dict[str, tuple[str, str]] = {
    "completeness": ("Architectural completeness",
                     "Orphan rate in canonical-named modules — Kimera's hidden dead code."),
    "interface": ("Interface contract",
                  "OrchestratorResult field-contract violations — does the substrate keep its own API."),
    "code_quality": ("Code quality",
                     "SonarQube static-analysis scan of the substrate."),
    "throughput": ("Throughput / cost",
                   "Per-cycle wall-time ceiling — cost-regression watch."),
    "reproducibility": ("Reproducibility",
                        "Deterministic-seed audit — same seed, same result."),
}


def list_cockpit_impl(proofs_root: str | Path = "proofs") -> dict[str, Any]:
    """Engineering-facet health, with a per-commit timeline per check.

    Read-only + best-effort. Each check gathers *all* its signed proofs
    (not just the latest) into a time-ordered series so the console can
    show the trend across substrate commits. Checks with no proof surface
    as ``no_data`` — not an error.
    """
    from ophamin.measuring.proof.codec import iter_proofs

    scen_family = {name: getattr(SCENARIOS[name], "family", "") for name in SCENARIOS}
    series_by_family: dict[str, list[dict[str, Any]]] = {f: [] for f in _COCKPIT_CHECKS}
    scanned = 0
    root = Path(proofs_root)
    if root.is_dir():
        for p in iter_proofs(root):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            scanned += 1
            fam = scen_family.get(p.parent.parent.name, "")
            if fam not in _COCKPIT_CHECKS:
                continue
            v = d.get("verdict", {}) or {}
            thr = v.get("threshold", {}) or {}
            data = d.get("data", {}) or {}
            series_by_family[fam].append({
                "scenario": p.parent.parent.name,
                "outcome": v.get("outcome", ""),
                "observed": v.get("observed_value"),
                "metric": thr.get("metric", ""),
                "comparator": thr.get("comparator", ""),
                "threshold": thr.get("value"),
                "created_at": (d.get("identity", {}) or {}).get("created_at", ""),
                "substrate_commit": str(data.get("substrate_git_commit", ""))[:12],
            })

    checks: list[dict[str, Any]] = []
    passing = 0
    for fam, (name, desc) in _COCKPIT_CHECKS.items():
        series = sorted(series_by_family[fam], key=lambda x: str(x.get("created_at", "")))
        latest = series[-1] if series else None
        outcome = (latest or {}).get("outcome", "")
        status = (
            "validated" if outcome == "VALIDATED"
            else "refuted" if outcome == "REFUTED"
            else "inconclusive" if latest
            else "no_data"
        )
        if status == "validated":
            passing += 1
        checks.append({
            "id": fam,
            "name": name,
            "desc": desc,
            "status": status,
            "latest": latest,
            "series": series,
            "proof_count": len(series),
        })

    return {
        "count": len(checks),
        "checks": checks,
        "passing": passing,
        "measured": sum(1 for c in checks if c["status"] != "no_data"),
        "proofs_scanned": scanned,
        "framework_version": __version__,
    }


def get_scenario_claim_impl(name: str) -> dict[str, Any]:
    """Return a scenario's falsifiable claim + metadata.

    Constructs the scenario with default kwargs to materialise the
    claim. If the constructor requires arguments, returns
    ``claim_available: False`` with a structured reason; callers can
    pass kwargs to :func:`run_scenario_impl` directly.
    """
    if name not in SCENARIOS:
        raise ValueError(f"unknown scenario {name!r}")
    cls = SCENARIOS[name]
    try:
        instance = cls()
    except TypeError as exc:
        return {
            "name": name,
            "metadata": scenario_metadata(name),
            "claim_available": False,
            "claim_unavailable_reason": (
                f"scenario constructor requires arguments; cannot materialise "
                f"the claim from defaults ({exc})"
            ),
        }
    claim = instance.build_claim()
    return {
        "name": name,
        "metadata": scenario_metadata(name),
        "claim_available": True,
        "claim": {
            "statement": claim.statement,
            "operationalization": claim.operationalization,
            "threshold": {
                "metric": claim.threshold.metric,
                "comparator": claim.threshold.comparator,
                "value": claim.threshold.value,
                "units": claim.threshold.units,
            },
            "h0": claim.h0,
            "h1": claim.h1,
        },
    }


def verify_proof_impl(proof_json: str, sign_key_b64: str = "") -> dict[str, Any]:
    """Parse + verify a wire-form signed record.

    Returns a structured verdict + verification result. Does NOT raise
    on signature mismatch — the result is surfaced as
    ``verified: False`` so callers can introspect the proof's fields
    even when verification fails.

    Emits an OpenTelemetry span ``ophamin.proof.verify`` with
    attributes ``ophamin.proof.verified`` (bool), ``ophamin.proof.id``
    (sha256 hex), ``ophamin.verdict.outcome``, and increments the
    ``ophamin_proofs_verified_total`` counter.

    Raises:
        ValueError: only on malformed JSON or non-object top-level
            input. Signature mismatch is a normal result, not an error.
    """
    instr = OphaminInstrumentor.get()
    with instr.tracer.start_as_current_span("ophamin.proof.verify") as span:
        key = decode_sign_key(sign_key_b64)
        try:
            record_dict: Any = json.loads(proof_json)
        except json.JSONDecodeError as exc:
            span.set_status(Status(StatusCode.ERROR, "invalid_json"))
            raise ValueError(f"proof_json is not valid JSON: {exc}") from exc
        if not isinstance(record_dict, dict):
            span.set_status(Status(StatusCode.ERROR, "not_object"))
            raise ValueError("proof_json must decode to a JSON object")

        # Reconstruct the body that Python signed over (everything except
        # ``signature`` and ``proof_id``). Mirrors the Rust + JS ports'
        # body-for-signing semantics.
        body = {k: v for k, v in record_dict.items() if k not in ("signature", "proof_id")}
        canonical = _canonical(body).encode("utf-8")
        expected_hex = hmac.new(key, canonical, hashlib.sha256).hexdigest()
        sig = record_dict.get("signature", "")
        verified = isinstance(sig, str) and hmac.compare_digest(sig, expected_hex)
        proof_id = hashlib.sha256(canonical).hexdigest()

        verdict = record_dict.get("verdict") or {}
        outcome = verdict.get("outcome", "") if isinstance(verdict, dict) else ""

        span.set_attribute("ophamin.proof.verified", verified)
        span.set_attribute("ophamin.proof.id", proof_id)
        span.set_attribute("ophamin.verdict.outcome", outcome)
        if not verified:
            span.set_status(Status(StatusCode.ERROR, "signature_mismatch"))

        instr.proofs_verified.add(
            1,
            attributes={
                "verified": str(verified).lower(),
                "outcome": outcome,
            },
        )

        return {
            "verified": verified,
            "proof_id": proof_id,
            "schema_version": record_dict.get("schema_version", ""),
            "verdict": {
                "outcome": outcome,
                "observed_value": (
                    verdict.get("observed_value", None)
                    if isinstance(verdict, dict)
                    else None
                ),
                "reasoning": (
                    verdict.get("reasoning", "")
                    if isinstance(verdict, dict)
                    else ""
                ),
                "threshold": (
                    verdict.get("threshold", {})
                    if isinstance(verdict, dict)
                    else {}
                ),
            },
            "claim_statement": (record_dict.get("claim") or {}).get("statement", ""),
            "framework_versions": {
                "ophamin_version_in_record": (record_dict.get("identity") or {}).get(
                    "ophamin_version", ""
                ),
                "ophamin_version_in_server": __version__,
            },
        }


def canonicalize_value_impl(
    value_json: str, sign_key_b64: str = ""
) -> dict[str, Any]:
    """Canonicalise any JSON value and compute its HMAC-SHA256.

    The default ``sign_key_b64`` is empty, in which case the framework-
    wide ``DEFAULT_SIGN_KEY`` is used. Pass a custom key when verifying
    against alternative deployment signatures.

    Emits an ``ophamin.canonical.encode`` span with
    ``ophamin.canonical.bytes`` attribute and records the byte length
    on the ``ophamin_canonical_bytes_encoded`` histogram.
    """
    instr = OphaminInstrumentor.get()
    with instr.tracer.start_as_current_span("ophamin.canonical.encode") as span:
        key = decode_sign_key(sign_key_b64)
        try:
            value = json.loads(value_json)
        except json.JSONDecodeError as exc:
            span.set_status(Status(StatusCode.ERROR, "invalid_json"))
            raise ValueError(f"value_json is not valid JSON: {exc}") from exc

        canonical = _canonical(value)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        mac = hmac.new(key, canonical.encode("utf-8"), hashlib.sha256).hexdigest()
        span.set_attribute("ophamin.canonical.bytes", len(canonical))
        instr.canonical_bytes.record(len(canonical))
        return {
            "canonical": canonical,
            "canonical_bytes_len": len(canonical),
            "sha256_hex": digest,
            "hmac_sha256_hex": mac,
            "content_hash": content_hash(value),
        }


def read_proof_index_impl(directory: str) -> dict[str, Any]:
    """Walk a directory tree and index every signed proof under it.

    Returns per-scenario counts, verdict distribution, and proof_ids.
    Does NOT verify signatures (use :func:`verify_proof_impl` on
    individual records for that).
    """
    root = Path(directory).expanduser()
    if not root.exists():
        raise ValueError(f"directory does not exist: {directory!r}")
    if not root.is_dir():
        raise ValueError(f"path is not a directory: {directory!r}")

    proofs: list[dict[str, Any]] = []
    scenarios: dict[str, dict[str, Any]] = {}
    for path in iter_proofs(root):
        try:
            rec = load(path)
        except Exception as exc:
            proofs.append(
                {
                    "path": str(path),
                    "error": f"failed to load: {type(exc).__name__}: {exc}",
                }
            )
            continue
        scen = rec.evidence[0].pillar if rec.evidence else "(no evidence)"
        outcome = rec.verdict.outcome
        proofs.append(
            {
                "path": str(path),
                "scenario_pillar": scen,
                "verdict": outcome,
                "proof_id_prefix": rec.proof_id[:16],
                "schema_version": rec.schema_version,
            }
        )
        bucket = scenarios.setdefault(scen, {"count": 0, "by_verdict": {}})
        bucket["count"] += 1
        bucket["by_verdict"][outcome] = bucket["by_verdict"].get(outcome, 0) + 1

    return {
        "directory": str(root),
        "total_proofs": sum(1 for p in proofs if "error" not in p),
        "load_errors": sum(1 for p in proofs if "error" in p),
        "by_scenario": scenarios,
        "proofs": proofs,
    }


def run_scenario_impl(name: str, kwargs_json: str = "{}") -> dict[str, Any]:
    """Construct + run a scenario and return its signed-proof summary.

    Warning: this is the heaviest tool exposed. Scenarios may run for
    tens of seconds to many minutes. Use sparingly.

    Args:
        name: scenario registered name.
        kwargs_json: JSON-encoded dict of constructor kwargs. Pass
            ``"{}"`` for default construction.

    Returns:
        A summary dict (NOT the full proof — proofs may be tens of KB
        and would overwhelm MCP transports). Persist server-side if you
        need the full record.
    """
    if name not in SCENARIOS:
        raise ValueError(f"unknown scenario {name!r}")
    cls = SCENARIOS[name]
    try:
        kwargs: Any = json.loads(kwargs_json) if kwargs_json else {}
    except json.JSONDecodeError as exc:
        raise ValueError(f"kwargs_json is not valid JSON: {exc}") from exc
    if not isinstance(kwargs, dict):
        raise ValueError("kwargs_json must decode to a JSON object")

    instr = OphaminInstrumentor.get()
    meta = scenario_metadata(name)
    with instr.tracer.start_as_current_span(f"ophamin.scenario.run.{name}") as span:
        span.set_attribute("ophamin.scenario.name", name)
        span.set_attribute("ophamin.scenario.family", meta.get("family", ""))
        span.set_attribute("ophamin.scenario.tier", meta.get("tier", ""))
        span.set_attribute("ophamin.scenario.target", meta.get("target", ""))

        instance = cls(**kwargs)
        # Cross-framework scenarios ignore the substrate (they have their own
        # oracle); other scenarios (Tier.SCIENTIFIC, etc.) read from it.
        # Pass a deterministic MockSubstrate so both shapes work without the
        # caller having to know which tier they're invoking.
        substrate = MockSubstrate(seed=1)
        t0 = time.perf_counter()
        try:
            proof = instance.run(substrate=substrate)
        except Exception as exc:
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            span.record_exception(exc)
            instr.scenarios_run.add(
                1,
                attributes={
                    "scenario": name,
                    "family": meta.get("family", ""),
                    "tier": meta.get("tier", ""),
                    "outcome": "EXCEPTION",
                },
            )
            raise
        duration = time.perf_counter() - t0
        instr.scenario_duration.record(
            duration,
            attributes={"scenario": name, "family": meta.get("family", "")},
        )

        span.set_attribute("ophamin.verdict.outcome", proof.verdict.outcome)
        span.set_attribute(
            "ophamin.verdict.observed_value", proof.verdict.observed_value
        )
        span.set_attribute("ophamin.proof.id", proof.proof_id)
        # Status from verdict: VALIDATED/INCONCLUSIVE are OK from
        # the framework's POV (the scenario completed normally);
        # REFUTED is also OK at the span level (a refutation is a
        # successful experimental outcome, not an error). Only
        # exceptions flip the span to ERROR.
        instr.scenarios_run.add(
            1,
            attributes={
                "scenario": name,
                "family": meta.get("family", ""),
                "tier": meta.get("tier", ""),
                "outcome": proof.verdict.outcome,
            },
        )

        return {
            "scenario": name,
            "verdict": {
                "outcome": proof.verdict.outcome,
                "observed_value": proof.verdict.observed_value,
                "threshold": {
                    "metric": proof.verdict.threshold.metric,
                    "comparator": proof.verdict.threshold.comparator,
                    "value": proof.verdict.threshold.value,
                },
                "reasoning": proof.verdict.reasoning,
            },
            "proof_id": proof.proof_id,
            "signature_prefix": proof.signature[:16],
            "claim_statement": proof.claim.statement,
            "n_evidence_pillars": len(proof.evidence),
            "framework_version": __version__,
        }
