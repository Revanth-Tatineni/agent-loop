"""Connects to the tools MCP server (tools/server.py) as a subprocess over stdio, discovers
its tools, and exposes them in two shapes the agent loop needs: Anthropic tool-use schemas
(for the `tools=` parameter of messages.create) and a plain async call(name, arguments) -> str
for after the model picks one.
"""

from __future__ import annotations

import sys
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


class MCPToolClient:
    def __init__(
        self,
        *,
        command: str | None = None,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self._command = command or sys.executable
        self._args = args or ["-m", "agent_loop.tools.server"]
        self._env = env
        self._stack = AsyncExitStack()
        self._session: ClientSession | None = None
        self._tools: dict[str, dict[str, Any]] = {}

    async def connect(self) -> None:
        params = StdioServerParameters(command=self._command, args=self._args, env=self._env)
        read, write = await self._stack.enter_async_context(stdio_client(params))
        self._session = await self._stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()
        result = await self._session.list_tools()
        self._tools = {
            tool.name: {
                "name": tool.name,
                "description": tool.description or "",
                "input_schema": tool.input_schema,
            }
            for tool in result.tools
        }

    async def close(self) -> None:
        await self._stack.aclose()

    @property
    def tool_names(self) -> set[str]:
        return set(self._tools)

    def tool_schemas(self, allowed: set[str] | None = None) -> list[dict[str, Any]]:
        names = self._tools if allowed is None else [n for n in self._tools if n in allowed]
        return [self._tools[name] for name in names]

    async def call(self, name: str, arguments: dict[str, Any]) -> str:
        if self._session is None:
            raise RuntimeError("connect() must be called before call()")
        result = await self._session.call_tool(name, arguments)
        text = "\n".join(block.text for block in result.content if hasattr(block, "text"))
        if result.is_error:
            return f"ERROR: {text or 'tool call failed'}"
        return text

    async def __aenter__(self) -> MCPToolClient:
        await self.connect()
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.close()
