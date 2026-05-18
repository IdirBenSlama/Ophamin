"""FastMCP server exposing Ophamin's read + run + verify surfaces.

This module is the interop counterpart to RFC 0002 Phase E9. Where
E9 ports (Rust ``ophamin-proof`` / JS ``@ophamin/proof``) let
non-Python systems READ + VERIFY Python-emitted signed records, this
MCP server lets non-Python agents DRIVE Python scenario execution
and signature operations.

Tool catalogue (read-only unless noted):

- ``list_scenarios()`` — every scenario in the registry with
  ``name`` / ``family`` / ``tier`` / ``target`` / ``goal`` metadata.
- ``get_scenario_claim(name)`` — the falsifiable-claim five-tuple
  (statement / operationalization / threshold / H0 / H1) plus
  scenario-level metadata.
- ``verify_proof(proof_json, sign_key_b64)`` — parse a wire-form
  signed record, verify the HMAC under the given key (default
  ``DEFAULT_SIGN_KEY``), and return the verdict + content-addressed
  ``proof_id``.
- ``canonicalize_value(value_json, sign_key_b64)`` — produce the
  canonical UTF-8 bytes of any JSON-serialisable value plus its
  HMAC-SHA256 under ``sign_key_b64`` (default test key). Useful
  for understanding what the encoder does without running a full
  scenario.
- ``read_proof_index(directory)`` — index every signed proof under
  a directory tree, returning per-scenario counts + verdict
  distributions.
- ``run_scenario(name, kwargs_json)`` — **NOT READ-ONLY**. Run a
  scenario with the given kwargs and return the resulting signed
  proof (truncated to a summary if the proof is large). This is
  the heaviest tool; use sparingly.

The server is named ``ophamin`` in the MCP catalogue. Clients
connect over stdio by default (what Claude Code expects); SSE +
streamable-HTTP are also supported via the CLI ``--transport`` flag.

Cross-reference: the read-only tools mirror the public APIs of
``@ophamin/proof`` and ``ophamin-proof`` so MCP-side semantics
match what a Rust/JS consumer would see.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from ophamin import __version__
from ophamin.measuring.proof.codec import iter_proofs, load
from ophamin.measuring.proof.record import _canonical, content_hash
from ophamin.measuring.scenarios.base import DEFAULT_SIGN_KEY, SCENARIOS, Tier
from ophamin.seeing.substrate.mock import MockSubstrate

#: Public server identity. Reused by ``ophamin.mcp.__init__`` and the CLI.
SERVER_NAME: str = "ophamin"
SERVER_TITLE: str = "Ophamin — signed empirical-proof framework"
SERVER_VERSION: str = __version__


# --------------------------------------------------------------------------
# Helper: decode an optional base64-encoded signing key argument
# --------------------------------------------------------------------------


def _decode_sign_key(sign_key_b64: str) -> bytes:
    """Return the bytes of a signing key, either from base64 or the default.

    MCP tool arguments are JSON-friendly strings; raw bytes don't pass
    cleanly. The convention: callers base64-encode their signing key
    and pass it as ``sign_key_b64``. Empty string → use Ophamin's
    framework-wide ``DEFAULT_SIGN_KEY``.
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


# --------------------------------------------------------------------------
# Tool implementations (registered onto FastMCP by build_server())
# --------------------------------------------------------------------------


def _scenario_metadata(name: str) -> dict[str, Any]:
    """Read-only metadata for a single scenario class."""
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


def _list_scenarios_impl() -> dict[str, Any]:
    scenarios = [_scenario_metadata(name) for name in sorted(SCENARIOS)]
    return {
        "count": len(scenarios),
        "scenarios": scenarios,
        "framework_version": __version__,
    }


def _get_scenario_claim_impl(name: str) -> dict[str, Any]:
    if name not in SCENARIOS:
        raise ValueError(f"unknown scenario {name!r}")
    cls = SCENARIOS[name]
    # Construct with default kwargs to materialise the build_claim.
    # Most scenarios accept zero-arg construction; if a particular
    # scenario requires arguments, callers can use ``run_scenario``
    # with explicit kwargs instead.
    try:
        instance = cls()
    except TypeError as exc:
        return {
            "name": name,
            "metadata": _scenario_metadata(name),
            "claim_available": False,
            "claim_unavailable_reason": (
                f"scenario constructor requires arguments; cannot materialise "
                f"the claim from defaults ({exc})"
            ),
        }
    claim = instance.build_claim()
    return {
        "name": name,
        "metadata": _scenario_metadata(name),
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


def _verify_proof_impl(proof_json: str, sign_key_b64: str = "") -> dict[str, Any]:
    """Parse + verify a wire-form signed record.

    Returns a structured verdict + verification result. Does NOT raise
    on signature mismatch — the result is surfaced as ``verified: False``
    so callers can introspect the proof's fields even when verification
    fails.
    """
    key = _decode_sign_key(sign_key_b64)
    try:
        record_dict: dict[str, Any] = json.loads(proof_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"proof_json is not valid JSON: {exc}") from exc
    if not isinstance(record_dict, dict):
        raise ValueError("proof_json must decode to a JSON object")

    # Reconstruct the body that Python signed over (everything except
    # ``signature`` and ``proof_id``). Mirrors the Rust + JS ports'
    # bodyForSigning / build_body_value semantics.
    body = {k: v for k, v in record_dict.items() if k not in ("signature", "proof_id")}
    canonical = _canonical(body).encode("utf-8")
    expected_hex = hmac.new(key, canonical, hashlib.sha256).hexdigest()
    sig = record_dict.get("signature", "")
    verified = isinstance(sig, str) and hmac.compare_digest(sig, expected_hex)
    proof_id = hashlib.sha256(canonical).hexdigest()

    verdict = record_dict.get("verdict") or {}

    return {
        "verified": verified,
        "proof_id": proof_id,
        "schema_version": record_dict.get("schema_version", ""),
        "verdict": {
            "outcome": verdict.get("outcome", ""),
            "observed_value": verdict.get("observed_value", None),
            "reasoning": verdict.get("reasoning", ""),
            "threshold": verdict.get("threshold", {}),
        },
        "claim_statement": (record_dict.get("claim") or {}).get("statement", ""),
        "framework_versions": {
            "ophamin_version_in_record": (record_dict.get("identity") or {}).get(
                "ophamin_version", ""
            ),
            "ophamin_version_in_server": __version__,
        },
    }


def _canonicalize_value_impl(
    value_json: str, sign_key_b64: str = ""
) -> dict[str, Any]:
    """Canonicalise any JSON value and compute its HMAC-SHA256.

    The default ``sign_key_b64`` is empty, in which case the framework-
    wide ``DEFAULT_SIGN_KEY`` is used. Pass a custom key when verifying
    against alternative deployment signatures.
    """
    key = _decode_sign_key(sign_key_b64)
    try:
        value = json.loads(value_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"value_json is not valid JSON: {exc}") from exc

    canonical = _canonical(value)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    mac = hmac.new(key, canonical.encode("utf-8"), hashlib.sha256).hexdigest()
    return {
        "canonical": canonical,
        "canonical_bytes_len": len(canonical),
        "sha256_hex": digest,
        "hmac_sha256_hex": mac,
        "content_hash": content_hash(value),
    }


def _read_proof_index_impl(directory: str) -> dict[str, Any]:
    """Walk a directory tree and index every signed proof under it.

    Returns per-scenario counts, verdict distribution, and proof_ids.
    Does NOT verify signatures (use ``verify_proof`` on individual
    records for that).
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
        scen = (
            rec.evidence[0].pillar
            if rec.evidence
            else "(no evidence)"
        )
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
        bucket = scenarios.setdefault(
            scen, {"count": 0, "by_verdict": {}}
        )
        bucket["count"] += 1
        bucket["by_verdict"][outcome] = bucket["by_verdict"].get(outcome, 0) + 1

    return {
        "directory": str(root),
        "total_proofs": sum(1 for p in proofs if "error" not in p),
        "load_errors": sum(1 for p in proofs if "error" in p),
        "by_scenario": scenarios,
        "proofs": proofs,
    }


def _run_scenario_impl(name: str, kwargs_json: str = "{}") -> dict[str, Any]:
    """Construct + run a scenario and return its signed proof.

    Warning: this is the heaviest tool exposed. Scenarios may run
    for tens of seconds to many minutes. Use sparingly.

    Args:
        name: scenario registered name (per ``list_scenarios``).
        kwargs_json: JSON-encoded dict of constructor kwargs. Pass
            ``"{}"`` for default construction.
    """
    if name not in SCENARIOS:
        raise ValueError(f"unknown scenario {name!r}")
    cls = SCENARIOS[name]
    try:
        kwargs: dict[str, Any] = json.loads(kwargs_json) if kwargs_json else {}
    except json.JSONDecodeError as exc:
        raise ValueError(f"kwargs_json is not valid JSON: {exc}") from exc
    if not isinstance(kwargs, dict):
        raise ValueError("kwargs_json must decode to a JSON object")

    instance = cls(**kwargs)
    # Cross-framework scenarios ignore the substrate (they have their own
    # oracle); other scenarios (Tier.SCIENTIFIC, etc.) read from it. Pass
    # a deterministic MockSubstrate so both shapes work without the caller
    # having to know which tier they're invoking.
    substrate = MockSubstrate(seed=1)
    proof = instance.run(substrate=substrate)
    # Surface a concise summary — the full proof can be tens of KB
    # and overwhelms MCP transports. Callers needing the full record
    # should persist it server-side and pass back a path.
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


# --------------------------------------------------------------------------
# build_server() — assemble the FastMCP instance with all tools registered.
# --------------------------------------------------------------------------


def build_server() -> FastMCP:
    """Construct and return a configured :class:`FastMCP` instance.

    All tools are registered before return. Caller is responsible for
    invoking ``mcp.run(transport=...)``.
    """
    mcp = FastMCP(
        SERVER_NAME,
        instructions=(
            "Ophamin exposes a falsifiability-first experimentation "
            "framework over MCP. Use ``list_scenarios`` to enumerate "
            "what's available, ``get_scenario_claim`` to inspect a "
            "scenario's pre-registered falsifiable claim, "
            "``verify_proof`` to verify a wire-form signed record's "
            "HMAC, ``canonicalize_value`` to produce canonical bytes + "
            "HMAC for any value, ``read_proof_index`` to triage a "
            "directory of records, and ``run_scenario`` (heavy) to "
            "drive a scenario and obtain a signed proof. The signing "
            "key is base64-encoded in tool arguments; empty string "
            "uses Ophamin's framework-wide DEFAULT_SIGN_KEY."
        ),
    )

    @mcp.tool(
        name="list_scenarios",
        description=(
            "Enumerate every scenario in Ophamin's registry, returning "
            "name / family / tier / target / goal metadata for each. "
            "Read-only and fast."
        ),
    )
    def list_scenarios() -> dict[str, Any]:
        return _list_scenarios_impl()

    @mcp.tool(
        name="get_scenario_claim",
        description=(
            "Return a scenario's falsifiable-claim five-tuple "
            "(statement / operationalization / threshold / H0 / H1) "
            "plus its metadata. The threshold is the load-bearing "
            "pass/fail boundary — every scenario MUST declare one. "
            "Read-only and fast."
        ),
    )
    def get_scenario_claim(name: str) -> dict[str, Any]:
        return _get_scenario_claim_impl(name)

    @mcp.tool(
        name="verify_proof",
        description=(
            "Verify a wire-form Ophamin signed proof. Argument: the "
            "JSON text of an EmpiricalProofRecord. Optional: a "
            "base64-encoded signing key (default: framework-wide key). "
            "Returns {verified, proof_id, schema_version, verdict, "
            "claim_statement, framework_versions}. Does NOT raise on "
            "signature mismatch — callers can introspect verdict fields "
            "even on a failed verify."
        ),
    )
    def verify_proof(
        proof_json: str, sign_key_b64: str = ""
    ) -> dict[str, Any]:
        return _verify_proof_impl(proof_json, sign_key_b64)

    @mcp.tool(
        name="canonicalize_value",
        description=(
            "Produce the canonical UTF-8 byte representation of any "
            "JSON value plus its HMAC-SHA256. Implements SCHEMAS.md "
            "R1–R11 byte-for-byte. Default sign key is the framework's "
            "DEFAULT_SIGN_KEY; pass base64-encoded sign_key_b64 to "
            "use a deployment-specific key."
        ),
    )
    def canonicalize_value(
        value_json: str, sign_key_b64: str = ""
    ) -> dict[str, Any]:
        return _canonicalize_value_impl(value_json, sign_key_b64)

    @mcp.tool(
        name="read_proof_index",
        description=(
            "Walk a directory tree and return an index of every signed "
            "proof under it, including per-scenario counts and verdict "
            "distributions. Does NOT verify signatures — combine with "
            "verify_proof on individual records for cryptographic "
            "confirmation."
        ),
    )
    def read_proof_index(directory: str) -> dict[str, Any]:
        return _read_proof_index_impl(directory)

    @mcp.tool(
        name="run_scenario",
        description=(
            "WARNING: heavyweight. Construct + run a scenario with the "
            "given JSON-encoded kwargs and return a summary of the "
            "resulting signed proof. Scenarios may run for tens of "
            "seconds to many minutes; the full proof is NOT returned "
            "(only a structured summary). Persist the proof server-side "
            "if you need the full record."
        ),
    )
    def run_scenario(name: str, kwargs_json: str = "{}") -> dict[str, Any]:
        return _run_scenario_impl(name, kwargs_json)

    return mcp


__all__ = [
    "SERVER_NAME",
    "SERVER_TITLE",
    "SERVER_VERSION",
    "build_server",
]
