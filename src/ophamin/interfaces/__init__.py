"""Shared transport-agnostic tool implementations.

This subpackage holds the load-bearing logic behind Ophamin's
agent-facing + microservice interop surfaces:

- ``ophamin.mcp`` — MCP server (Claude Code / Desktop / Cursor / ...)
- ``ophamin.http_api`` — FastAPI REST surface (any HTTP consumer)

Both wrap the same pure functions from ``interfaces._impls`` so a
behavioural change lands in one place. The implementations are
read-only-by-default; the one heavyweight tool (``run_scenario``)
is explicitly marked.

Functions in this module:

- ``list_scenarios()``: enumerate every scenario registered in
  ``SCENARIOS`` with metadata.
- ``get_scenario_claim(name)``: return a scenario's falsifiable
  claim five-tuple.
- ``verify_proof(proof_json, sign_key_b64)``: parse + HMAC-verify
  a wire-form record. Does NOT raise on signature mismatch.
- ``canonicalize_value(value_json, sign_key_b64)``: canonical UTF-8
  bytes + HMAC of any JSON value.
- ``read_proof_index(directory)``: per-scenario counts + verdict
  distribution from a tree of signed records.
- ``run_scenario(name, kwargs_json)``: **HEAVY** — construct + run
  a scenario, return signed-proof summary.

All take string arguments (JSON-friendly so they round-trip cleanly
through MCP / HTTP / any future transport). The sign-key argument
``sign_key_b64`` is base64-encoded bytes; empty string defaults to
the framework-wide ``DEFAULT_SIGN_KEY``.
"""

from __future__ import annotations

from ophamin.interfaces._impls import (
    decode_sign_key,
    canonicalize_value_impl,
    get_scenario_claim_impl,
    list_scenarios_impl,
    read_proof_index_impl,
    run_scenario_impl,
    scenario_metadata,
    verify_proof_impl,
)

__all__ = [
    "decode_sign_key",
    "canonicalize_value_impl",
    "get_scenario_claim_impl",
    "list_scenarios_impl",
    "read_proof_index_impl",
    "run_scenario_impl",
    "scenario_metadata",
    "verify_proof_impl",
]
