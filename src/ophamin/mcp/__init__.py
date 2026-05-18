"""Ophamin's Model Context Protocol (MCP) server.

This subpackage exposes Ophamin's read + run + verify surfaces over
the Model Context Protocol so any MCP client (Claude Code,
Claude Desktop, Cursor, Cline, custom agents) can drive scenarios
and verify signed proofs without a Python integration.

It is the **interop-platform counterpart** to RFC 0002 Phase E9's
cross-language READ APIs (the Rust `ophamin-proof` and JS/TS
`@ophamin/proof` ports): E9 lets non-Python systems VERIFY
Python-emitted records; this MCP server lets non-Python agents
DRIVE Python scenario execution + canonical-form / signature
operations as well.

Usage from a CLI:

```bash
ophamin mcp serve              # stdio transport (default; what Claude Code expects)
ophamin mcp serve --transport sse                # SSE transport
ophamin mcp serve --transport streamable-http    # streamable HTTP
```

Usage as a library:

```python
from ophamin.mcp import build_server

mcp = build_server()
mcp.run(transport="stdio")
```

See ``src/ophamin/mcp/server.py`` for the tool catalogue and the
``mcp/README.md`` for client wiring recipes.
"""

from __future__ import annotations

from ophamin.mcp.server import (
    SERVER_NAME,
    SERVER_TITLE,
    SERVER_VERSION,
    build_server,
)

__all__ = ["build_server", "SERVER_NAME", "SERVER_TITLE", "SERVER_VERSION"]
