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

from typing import Any

from mcp.server.fastmcp import FastMCP

from ophamin import __version__
from ophamin.interfaces._impls import (
    canonicalize_value_impl as _canonicalize_value_shared,
    decode_sign_key as _decode_sign_key_shared,
    get_scenario_claim_impl as _get_scenario_claim_shared,
    list_scenarios_impl as _list_scenarios_shared,
    read_proof_index_impl as _read_proof_index_shared,
    run_scenario_impl as _run_scenario_shared,
    scenario_metadata as _scenario_metadata_shared,
    verify_proof_impl as _verify_proof_shared,
)

#: Public server identity. Reused by ``ophamin.mcp.__init__`` and the CLI.
SERVER_NAME: str = "ophamin"
SERVER_TITLE: str = "Ophamin — signed empirical-proof framework"
SERVER_VERSION: str = __version__


# --------------------------------------------------------------------------
# Backwards-compatible aliases for the underscore-prefixed names that
# 0.17.x tests and other callers may import from this module directly.
# The load-bearing logic now lives in ``ophamin.interfaces._impls`` so
# the FastAPI HTTP server (added in 0.18.0) can share it.
# --------------------------------------------------------------------------

_decode_sign_key = _decode_sign_key_shared
_scenario_metadata = _scenario_metadata_shared
_list_scenarios_impl = _list_scenarios_shared
_get_scenario_claim_impl = _get_scenario_claim_shared
_verify_proof_impl = _verify_proof_shared
_canonicalize_value_impl = _canonicalize_value_shared
_read_proof_index_impl = _read_proof_index_shared
_run_scenario_impl = _run_scenario_shared


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
