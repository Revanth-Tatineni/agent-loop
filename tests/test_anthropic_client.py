from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from llmtrace import get_default_storage

from agent_loop.anthropic_client import AnthropicTurnClient, _parse_turn


def _text_block(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def _tool_use_block(block_id: str, name: str, tool_input: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=block_id, name=name, input=tool_input)


def test_parse_turn_extracts_text_only():
    response = SimpleNamespace(content=[_text_block("hello")])
    result = _parse_turn(response)
    assert result.text == "hello"
    assert result.tool_call is None


def test_parse_turn_extracts_first_tool_call_and_ignores_extra_ones():
    response = SimpleNamespace(
        content=[
            _text_block("I should search"),
            _tool_use_block("id1", "web_search", {"query": "x"}),
            _tool_use_block("id2", "fetch_url", {"url": "y"}),
        ]
    )
    result = _parse_turn(response)
    assert result.text == "I should search"
    assert result.tool_call is not None
    assert result.tool_call.name == "web_search"
    assert result.tool_call.id == "id1"
    assert result.tool_call.arguments == {"query": "x"}


class _FakeMessages:
    def __init__(self, response: Any) -> None:
        self._response = response
        self.last_kwargs: dict[str, Any] = {}

    def create(self, **kwargs: Any) -> Any:
        self.last_kwargs = kwargs
        return self._response


class _FakeAnthropicClient:
    def __init__(self, response: Any) -> None:
        self.messages = _FakeMessages(response)


def test_anthropic_turn_client_records_cost_and_tokens_via_llmtrace():
    response = SimpleNamespace(
        content=[_text_block("done")],
        usage=SimpleNamespace(input_tokens=100, output_tokens=50),
    )
    client = AnthropicTurnClient(_FakeAnthropicClient(response), model="claude-sonnet-5")

    result = client.turn([{"role": "user", "content": "hi"}], [], project="test-project")

    assert result.text == "done"
    rows = get_default_storage().query(project="test-project")
    assert len(rows) == 1
    assert rows[0].input_tokens == 100
    assert rows[0].output_tokens == 50
    assert rows[0].cost_usd > 0


def test_anthropic_turn_client_passes_model_and_tools_through():
    usage = SimpleNamespace(input_tokens=1, output_tokens=1)
    response = SimpleNamespace(content=[_text_block("ok")], usage=usage)
    fake_client = _FakeAnthropicClient(response)
    client = AnthropicTurnClient(fake_client, model="claude-sonnet-5")

    tool_schemas = [{"name": "web_search", "description": "", "input_schema": {}}]
    client.turn([{"role": "user", "content": "hi"}], tool_schemas, project="p")

    assert fake_client.messages.last_kwargs["model"] == "claude-sonnet-5"
    assert fake_client.messages.last_kwargs["tools"] == tool_schemas
