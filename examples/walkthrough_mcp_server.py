"""Concept walkthrough — Model Context Protocol server (RFC 0002 Phase E9.3).

Demonstrates the **AI-agent interop layer**: any MCP client
(Claude Code, Claude Desktop, Cursor, Cline, or any generic
stdio-speaking MCP client) can drive Ophamin's six core
capabilities — list scenarios, get a claim, verify a proof,
canonicalize a value, read the proof index, run a scenario.

The walkthrough exercises every tool through FastMCP's in-process
``call_tool`` path so no real subprocess plumbing is needed to
demonstrate the contract. In production the same server runs
under ``ophamin mcp serve`` (stdio by default; ``--sse`` or
``--streamable-http`` for other transports).

Run with::

    PYTHONPATH=src python examples/walkthrough_mcp_server.py

Requires the ``[mcp]`` extra. Safe to import; demo runs only as
``__main__``.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

try:
    import mcp  # noqa: F401  — presence check only
except ImportError:
    sys.exit(
        "This walkthrough requires the [mcp] extra. "
        "Install with: pip install 'ophamin[mcp]'"
    )

from ophamin.mcp import build_server


REPO_ROOT = Path(__file__).resolve().parent.parent
PROOFS_DIR = REPO_ROOT / "proofs" / "measurement_machinery"


def _extract_text(result: Any) -> str | None:
    """Pull the text content out of a FastMCP call_tool result.

    FastMCP's ``call_tool`` returns either ``(content_blocks,
    structured_result)`` or just ``content_blocks`` depending on
    whether structured output is enabled. We robustly find the
    first text-shaped piece.
    """
    if isinstance(result, tuple) and len(result) == 2:
        content_blocks, _ = result
    else:
        content_blocks = result
    if not content_blocks:
        return None
    block = content_blocks[0]
    text = getattr(block, "text", None)
    if text:
        return text
    if isinstance(block, dict) and "text" in block:
        return block["text"]
    return None


async def _call(server: Any, name: str, args: dict[str, Any]) -> Any:
    """Invoke an MCP tool by name and return the parsed JSON result."""
    result = await server.call_tool(name, args)
    text = _extract_text(result)
    if text is None:
        # Fall back to whatever the second tuple element holds.
        if isinstance(result, tuple) and len(result) == 2:
            return result[1]
        return result
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


async def amain() -> None:
    print("# MCP server walkthrough — RFC 0002 Phase E9.3")
    print()
    print("Ophamin's Model Context Protocol server exposes six tools to")
    print("any MCP-aware AI agent (Claude Code, Claude Desktop, Cursor,")
    print("Cline) — list scenarios, get a claim, verify a proof,")
    print("canonicalize a value, read the proof index, run a scenario.")
    print()
    print("This walkthrough exercises every tool through FastMCP's")
    print("in-process call_tool path. The tool implementations are the")
    print("SAME `ophamin.interfaces._impls` functions every other layer")
    print("uses, so behavioural drift between transports is structural.")

    server = build_server()

    # === Step 1: list_scenarios ===
    print("\n## Step 1: tool `list_scenarios`")
    result = await _call(server, "list_scenarios", {})
    scenarios = result.get("scenarios", [])
    print(f"  total scenarios: {len(scenarios)}")
    for s in scenarios[:3]:
        print(f"    - {s['name']:<32} tier={s.get('tier', '?')}")
    print(f"    ... ({len(scenarios) - 3} more)")
    assert len(scenarios) > 0
    scenario_name = scenarios[0]["name"]

    # === Step 2: get_scenario_claim ===
    print(f"\n## Step 2: tool `get_scenario_claim` (name={scenario_name})")
    result = await _call(
        server, "get_scenario_claim", {"name": scenario_name}
    )
    metadata = result.get("metadata", {})
    print(f"  scenario:   {result.get('name', '?')}")
    print(f"  tier:       {metadata.get('tier', '?')}")
    print(f"  target:     {metadata.get('target', '?')}")
    goal = metadata.get("goal", "?")
    print(f"  goal:       {goal[:80]}{'...' if len(goal) > 80 else ''}")

    # === Step 3: canonicalize_value ===
    print("\n## Step 3: tool `canonicalize_value`")
    value = {"alpha": 1, "beta": 2.5, "gamma": [3, 4]}
    value_json = json.dumps(value)
    result = await _call(
        server, "canonicalize_value", {"value_json": value_json}
    )
    print(f"  input:           {value_json}")
    print(f"  canonical:       {result['canonical']}")
    print(f"  sha256_hex:      {result['sha256_hex'][:32]}...")
    print(f"  hmac_sha256_hex: {result['hmac_sha256_hex'][:32]}...")

    # === Step 4: verify_proof ===
    proofs = sorted(PROOFS_DIR.rglob("*.json"))
    if not proofs:
        raise SystemExit("No shipped proofs found under proofs/measurement_machinery/")
    proof_path = proofs[0]
    print(f"\n## Step 4: tool `verify_proof` (proof: {proof_path.name})")
    proof_json = proof_path.read_text()
    result = await _call(server, "verify_proof", {"proof_json": proof_json})
    print(f"  verified:        {result['verified']}")
    print(f"  verdict.outcome: {result['verdict']['outcome']}")
    print(f"  proof_id:        {result['proof_id'][:32]}...")
    assert result["verified"] is True

    # === Step 5: read_proof_index ===
    print("\n## Step 5: tool `read_proof_index`")
    result = await _call(
        server, "read_proof_index", {"directory": str(PROOFS_DIR)}
    )
    print(f"  directory:    {result.get('directory', '?')}")
    print(f"  total_proofs: {result.get('total_proofs', 0)}")
    counts = result.get("counts_by_scenario", {})
    for name, count in list(counts.items())[:3]:
        print(f"    - {name}: {count}")

    # === Step 6: run_scenario ===
    print("\n## Step 6: tool `run_scenario`")
    print("  Running a small scenario (spearman-crosscheck, n_pairs=3,")
    print("  sample_size=20) end-to-end via the MCP tool path.")
    result = await _call(
        server,
        "run_scenario",
        {
            "name": "spearman-crosscheck",
            "kwargs_json": '{"n_pairs": 3, "sample_size": 20}',
        },
    )
    print(f"  scenario:        {result.get('scenario', '?')}")
    print(f"  verdict.outcome: {result.get('verdict', {}).get('outcome', '?')}")
    print(f"  proof_id:        {result.get('proof_id', '?')[:32]}...")
    assert result["verdict"]["outcome"] == "VALIDATED"

    # === Invariants — what we MUST pin ===
    assert scenario_name in {s["name"] for s in scenarios}
    assert result["scenario"] == "spearman-crosscheck"

    print("\n✓ MCP server walkthrough complete. Contract validated.")


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
