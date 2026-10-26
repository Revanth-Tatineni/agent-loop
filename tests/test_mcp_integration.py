"""Integration tests against the REAL tools MCP server, spawned as a real subprocess over
stdio -- this is the one place that proves the MCP wiring itself works, not just the plain
Python functions it calls. web_search/fetch_url aren't exercised here (that would need real
network access and would make CI flaky); the file tools and sandboxing are, since both are
network-free and are exactly the behavior worth protecting with a real end-to-end test.

Each test opens its own MCPToolClient with `async with` inside the test body, rather than
through a fixture that spans the yield -- anyio's cancel-scope tracking requires a task-group
to be entered and exited by the same asyncio Task, and a pytest-asyncio fixture's teardown can
run in a different Task than its setup. Keeping connect/close in one test body sidesteps that
entirely.
"""

from __future__ import annotations

import os

from agent_loop.mcp_client import MCPToolClient


def _env_for(tmp_path) -> dict[str, str]:
    return {**os.environ, "AGENT_LOOP_WORKSPACE": str(tmp_path)}


async def test_lists_the_four_expected_tools(tmp_path):
    async with MCPToolClient(env=_env_for(tmp_path)) as client:
        assert client.tool_names == {"web_search", "fetch_url", "write_file", "read_file"}


async def test_write_then_read_round_trip_through_real_mcp(tmp_path):
    async with MCPToolClient(env=_env_for(tmp_path)) as client:
        write_result = await client.call("write_file", {"path": "note.txt", "content": "hi there"})
        assert "wrote" in write_result
        assert (tmp_path / "note.txt").read_text() == "hi there"

        read_result = await client.call("read_file", {"path": "note.txt"})
        assert read_result == "hi there"


async def test_read_missing_file_comes_back_as_an_error_observation(tmp_path):
    async with MCPToolClient(env=_env_for(tmp_path)) as client:
        result = await client.call("read_file", {"path": "missing.txt"})
        assert result.startswith("ERROR")


async def test_path_traversal_through_the_real_tool_call_is_blocked(tmp_path):
    async with MCPToolClient(env=_env_for(tmp_path)) as client:
        result = await client.call("write_file", {"path": "../escape.txt", "content": "no"})
        assert result.startswith("ERROR")
        assert not (tmp_path.parent / "escape.txt").exists()
