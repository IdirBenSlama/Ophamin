# Ophamin MCP server

> Expose Ophamin's read + run + verify surfaces over the
> [Model Context Protocol](https://modelcontextprotocol.io/) so any
> MCP client (Claude Code, Claude Desktop, Cursor, Cline, custom
> agents) can drive scenarios and verify signed proofs without a
> Python integration.

This is the interop-platform counterpart to RFC 0002 Phase E9's
cross-language READ APIs. E9 lets non-Python *systems* verify
Python-emitted records; the MCP server lets non-Python *agents*
drive Python scenario execution + signature operations as well.

## Tool catalogue

| Tool | Purpose | Read-only |
|---|---|---|
| `list_scenarios` | Enumerate every scenario in the registry: name / family / tier / target / goal. | ✓ |
| `get_scenario_claim` | Return a scenario's falsifiable-claim five-tuple (statement / operationalization / threshold / H0 / H1). | ✓ |
| `verify_proof` | Parse + HMAC-verify a wire-form `EmpiricalProofRecord`. Returns the verdict + content-addressed `proof_id`. Does NOT raise on signature mismatch — surfaces the result. | ✓ |
| `canonicalize_value` | Produce canonical UTF-8 bytes + HMAC-SHA256 for any JSON value. Useful for understanding what the encoder does. | ✓ |
| `read_proof_index` | Walk a directory tree and index every signed proof, returning per-scenario counts + verdict distributions. | ✓ |
| `run_scenario` | **Heavyweight.** Construct + run a scenario and return a signed-proof summary. May take seconds to minutes. | ✗ |

All tools accept JSON-friendly arguments. Signing keys are passed
as base64-encoded strings; empty string uses Ophamin's framework-wide
`DEFAULT_SIGN_KEY`.

## Starting the server

The server is invoked as a CLI subcommand of `ophamin`:

```bash
# stdio transport — what Claude Code, Claude Desktop, and Cursor expect
ophamin mcp serve

# SSE transport (long-lived HTTP)
ophamin mcp serve --transport sse

# Streamable HTTP transport
ophamin mcp serve --transport streamable-http
```

Or programmatically from Python:

```python
from ophamin.mcp import build_server

mcp = build_server()
mcp.run(transport="stdio")
```

## Client wiring recipes

### Claude Code (.claude/config.json)

```jsonc
{
  "mcpServers": {
    "ophamin": {
      "command": "ophamin",
      "args": ["mcp", "serve"]
    }
  }
}
```

Or, if `ophamin` isn't on PATH (e.g. you installed it in a venv):

```jsonc
{
  "mcpServers": {
    "ophamin": {
      "command": "/absolute/path/to/.venv/bin/python",
      "args": ["-m", "ophamin.cli", "mcp", "serve"]
    }
  }
}
```

### Claude Desktop (claude_desktop_config.json)

Add under the top-level `mcpServers` key:

```jsonc
{
  "mcpServers": {
    "ophamin": {
      "command": "ophamin",
      "args": ["mcp", "serve"]
    }
  }
}
```

Then restart Claude Desktop. The Ophamin tools appear in the
hammer-icon menu.

### Cursor (.cursor/mcp.json)

```jsonc
{
  "mcpServers": {
    "ophamin": {
      "command": "ophamin",
      "args": ["mcp", "serve"]
    }
  }
}
```

### Cline / generic stdio clients

Any client that supports `command` + `args` invocation of an
MCP server can wire Ophamin the same way. The server speaks
JSON-RPC over stdio per the MCP base spec.

## Example tool invocations

These are what an agent would see when querying the server. The
exact JSON shape is what `FastMCP.call_tool` returns.

### Discover scenarios

```
> list_scenarios
{
  "count": 32,
  "scenarios": [
    {
      "name": "spearman-crosscheck",
      "family": "cross_framework",
      "tier": "MEASUREMENT_MACHINERY",
      "target": "scipy+pingouin-cross-framework",
      "goal": "Verify the Spearman rank-correlation implementation..."
    },
    ...
  ],
  "framework_version": "0.17.0"
}
```

### Read a claim

```
> get_scenario_claim(name="spearman-crosscheck")
{
  "name": "spearman-crosscheck",
  "claim_available": true,
  "claim": {
    "statement": "Across 30 synthetic (x, y) pairs of size 100...",
    "threshold": {
      "metric": "max_absolute_spearman_difference",
      "comparator": "<=",
      "value": 1e-09,
      "units": "correlation"
    },
    "h0": "scipy and pingouin disagree...",
    "h1": "Both libraries compute identical Spearman ρ..."
  },
  ...
}
```

### Verify a signed proof

```
> verify_proof(proof_json=<text of an Ophamin signed proof>)
{
  "verified": true,
  "proof_id": "f65319cb2ab7eb3d91fe455fd5cc6518...",
  "verdict": {
    "outcome": "VALIDATED",
    "observed_value": 0.0,
    "threshold": { ... }
  },
  "claim_statement": "Across 30 synthetic (x, y) pairs..."
}
```

### Canonicalize a value

```
> canonicalize_value(value_json='{"x": 30, "y": 30.0}')
{
  "canonical": "{\"x\":30,\"y\":30.0}",
  "canonical_bytes_len": 18,
  "sha256_hex": "...",
  "hmac_sha256_hex": "..."
}
```

Note the `30` vs `30.0` distinction is preserved through Ophamin's
canonical-form (per `SCHEMAS.md` R4 / R5) — Python integers do NOT
get a trailing `.0` while Python floats always do.

### Run a scenario

```
> run_scenario(name="spearman-crosscheck", kwargs_json='{"n_pairs": 10, "sample_size": 50}')
{
  "scenario": "spearman-crosscheck",
  "verdict": {
    "outcome": "VALIDATED",
    "observed_value": 0.0,
    "threshold": { "comparator": "<=", "value": 1e-09 },
    "reasoning": "10 pairs checked; max |rho_scipy - rho_pingouin| = 0.000e+00 (≤ 1e-09 tol)"
  },
  "proof_id": "...",
  "signature_prefix": "...",
  "claim_statement": "...",
  "n_evidence_pillars": 1,
  "framework_version": "0.17.0"
}
```

## Why this matters (interop reframe)

Ophamin's wire-format contract (`EmpiricalProofRecord`,
`SCHEMAS.md` R1–R11) is portable across languages — the Rust crate
and JS package verify Python-emitted signatures byte-for-byte.

The MCP server extends interop one more layer: any *agent* that
speaks MCP — regardless of its host language — can now:

- **Discover** what Ophamin can measure (`list_scenarios`).
- **Read** the claim before running anything (`get_scenario_claim`).
- **Drive** a measurement (`run_scenario`).
- **Verify** the resulting signed proof (`verify_proof`).
- **Index** an existing corpus of signed proofs (`read_proof_index`).
- **Inspect** the canonical-form machinery (`canonicalize_value`).

A Claude Code agent investigating a research-software validity
question can now reach for Ophamin tools as naturally as it reaches
for `Read` or `Grep`. Same for any future MCP-speaking agent.

## Versioning

The MCP server's version tracks the Ophamin framework release that
ships it (currently `0.17.0`). The tool catalogue is stable across
minor releases per the framework's
[`STABILITY.md`](../../../docs/STABILITY.md) contract — additions
land additively, removals follow the documented deprecation window.

## See also

- [`SCHEMAS.md`](../../../SCHEMAS.md) — normative wire-format spec the
  `verify_proof` + `canonicalize_value` tools implement.
- [`packages/ophamin-proof-js/README.md`](../../../packages/ophamin-proof-js/README.md) — JS/TS read-only port.
- [`crates/ophamin-proof/README.md`](../../../crates/ophamin-proof/README.md) — Rust read-only port.
- [Model Context Protocol spec](https://modelcontextprotocol.io/) — the protocol this server speaks.
