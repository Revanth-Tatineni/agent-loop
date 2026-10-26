"""Wraps the real Anthropic tool-use call with llmtrace (project 3), and parses the response
into a plain TurnResult the agent loop can act on without touching Anthropic SDK types
directly -- this is the one place the agent loop and the Anthropic SDK actually meet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from llmtrace import trace_call


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class TurnResult:
    text: str | None
    tool_call: ToolCall | None
    raw_content: list[dict[str, Any]] = field(default_factory=list)


class LLMTurn(Protocol):
    def turn(
        self,
        messages: list[dict[str, Any]],
        tool_schemas: list[dict[str, Any]],
        *,
        project: str,
    ) -> TurnResult: ...


class AnthropicTurnClient:
    """The real implementation. `client` is any object with a `.messages.create(...)` method
    shaped like the Anthropic SDK's -- in tests, a fake standing in for the SDK; at runtime,
    `anthropic.Anthropic()`."""

    def __init__(self, client: Any, model: str) -> None:
        self.client = client
        self.model = model

    def turn(
        self,
        messages: list[dict[str, Any]],
        tool_schemas: list[dict[str, Any]],
        *,
        project: str,
    ) -> TurnResult:
        with trace_call(
            provider="anthropic", model=self.model, operation="agent.turn", project=project
        ) as t:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=messages,
                tools=tool_schemas,
            )
            t.record_response(response)
            return _parse_turn(response)


def _parse_turn(response: Any) -> TurnResult:
    text_parts: list[str] = []
    tool_call: ToolCall | None = None
    raw_content: list[dict[str, Any]] = []
    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)
            raw_content.append({"type": "text", "text": block.text})
        elif block.type == "tool_use":
            raw_content.append(
                {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
            )
            if tool_call is None:  # only the first tool call in a turn is acted on
                tool_call = ToolCall(id=block.id, name=block.name, arguments=dict(block.input))
    return TurnResult(
        text=" ".join(text_parts) or None, tool_call=tool_call, raw_content=raw_content
    )
