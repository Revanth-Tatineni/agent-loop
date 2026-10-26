"""The MCP server exposing agent-loop's four tools: web_search, fetch_url, write_file,
read_file. Run standalone with `python -m agent_loop.tools.server` (stdio transport) --
mcp_client.py spawns exactly this as a subprocess and talks to it over stdin/stdout, the same
way any MCP client talks to any MCP server.
"""

from __future__ import annotations

import os
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from agent_loop.tools.fetch import fetch_text
from agent_loop.tools.files import read_sandboxed_file, write_sandboxed_file
from agent_loop.tools.search import duckduckgo_search

WORKSPACE_ROOT = Path(os.environ.get("AGENT_LOOP_WORKSPACE", "./workspace"))
WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)

mcp = MCPServer("agent-loop-tools")


@mcp.tool()
def web_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Search the web and return up to max_results results, each {title, url, snippet}."""
    return duckduckgo_search(query, max_results)


@mcp.tool()
def fetch_url(url: str, max_chars: int = 4000) -> str:
    """Fetch a URL and return its visible text content, truncated to max_chars."""
    return fetch_text(url, max_chars)


@mcp.tool()
def write_file(path: str, content: str) -> str:
    """Write content to a file inside the sandboxed workspace directory."""
    return write_sandboxed_file(WORKSPACE_ROOT, path, content)


@mcp.tool()
def read_file(path: str) -> str:
    """Read a file from the sandboxed workspace directory."""
    return read_sandboxed_file(WORKSPACE_ROOT, path)


if __name__ == "__main__":
    mcp.run()
