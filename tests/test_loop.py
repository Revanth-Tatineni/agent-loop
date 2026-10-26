from __future__ import annotations

import itertools
from typing import Any

import pytest
from llmtrace import get_default_storage
from llmtrace.models import TraceRecord

from agent_loop.anthropic_client import ToolCall, TurnResult
from agent_loop.guardrails import CostLimitExceeded, Guardrails, StepLimitExceeded, ToolNotAllowed
from agent_loop.loop import Agent
from agent_loop.trace_log import TraceLog, load_steps


class ScriptedLLM:
    """Cycles through a scripted sequence of TurnResults and records a fake llmtrace cost for
    each call, so the loop's cost-ceiling guardrail has something real to read without a real
    Anthropic API call."""

    def __init__(self, turns: list[TurnResult], cost_per_turn: float = 0.0) -> None:
        self._cycle = itertools.cycle(turns)
        self._cost_per_turn = cost_per_turn
        self.calls = 0

    def turn(
        self, messages: list[dict[str, Any]], tool_schemas: list[dict[str, Any]], *, project: str
    ) -> TurnResult:
        self.calls += 1
        record = TraceRecord(
            provider="fake", model="fake-model", operation="agent.turn", project=project
        )
        record.cost_usd = self._cost_per_turn
        get_default_storage().save(record)
        return next(self._cycle)


class FakeTools:
    def __init__(self, response: str = "observation") -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def tool_schemas(self, allowed: set[str] | None = None) -> list[dict[str, Any]]:
        return [{"name": "web_search", "description": "", "input_schema": {}}]

    async def call(self, name: str, arguments: dict[str, Any]) -> str:
        self.calls.append((name, arguments))
        return self.response


def _tool_call_turn(name: str = "web_search") -> TurnResult:
    return TurnResult(
        text="I should look this up",
        tool_call=ToolCall(id="t1", name=name, arguments={"query": "x"}),
        raw_content=[{"type": "tool_use", "id": "t1", "name": name, "input": {"query": "x"}}],
    )


def _final_turn(text: str = "done") -> TurnResult:
    return TurnResult(text=text, tool_call=None, raw_content=[{"type": "text", "text": text}])


async def test_agent_returns_final_answer_after_one_tool_call(tmp_path):
    llm = ScriptedLLM([_tool_call_turn(), _final_turn("the answer")])
    tools = FakeTools()
    agent = Agent(
        llm=llm,
        tools=tools,
        guardrails=Guardrails(max_steps=10),
        trace_log=TraceLog(tmp_path / "t.jsonl"),
    )

    answer = await agent.run("research something")

    assert answer == "the answer"
    assert len(tools.calls) == 1
    steps = load_steps(tmp_path / "t.jsonl")
    assert len(steps) == 2
    assert steps[-1].is_final is True
    assert steps[-1].final_answer == "the answer"


async def test_step_limit_guardrail_actually_stops_an_agent_that_never_finishes(tmp_path):
    llm = ScriptedLLM([_tool_call_turn()])  # cycles forever, never a final turn
    tools = FakeTools()
    agent = Agent(
        llm=llm,
        tools=tools,
        guardrails=Guardrails(max_steps=3),
        trace_log=TraceLog(tmp_path / "t.jsonl"),
    )

    with pytest.raises(StepLimitExceeded):
        await agent.run("loop forever")

    assert llm.calls == 3
    assert len(tools.calls) == 3
    steps = load_steps(tmp_path / "t.jsonl")
    assert len(steps) == 4
    assert steps[-1].is_final is True
    assert "StepLimitExceeded" in (steps[-1].stopped_reason or "")


async def test_cost_ceiling_guardrail_stops_before_the_tool_runs(tmp_path):
    llm = ScriptedLLM([_tool_call_turn()], cost_per_turn=1.0)
    tools = FakeTools()
    agent = Agent(
        llm=llm,
        tools=tools,
        guardrails=Guardrails(max_steps=10, cost_ceiling_usd=0.5),
        trace_log=TraceLog(tmp_path / "t.jsonl"),
    )

    with pytest.raises(CostLimitExceeded):
        await agent.run("expensive task")

    assert llm.calls == 1
    assert tools.calls == []  # the tool never ran -- cost is checked before the tool call
    steps = load_steps(tmp_path / "t.jsonl")
    assert len(steps) == 1
    assert "CostLimitExceeded" in (steps[0].stopped_reason or "")


async def test_tool_allowlist_guardrail_blocks_a_disallowed_tool(tmp_path):
    llm = ScriptedLLM([_tool_call_turn(name="write_file")])
    tools = FakeTools()
    agent = Agent(
        llm=llm,
        tools=tools,
        guardrails=Guardrails(max_steps=10, allowed_tools={"web_search"}),
        trace_log=TraceLog(tmp_path / "t.jsonl"),
    )

    with pytest.raises(ToolNotAllowed):
        await agent.run("try a disallowed tool")

    assert tools.calls == []


async def test_agent_run_leaves_real_rows_in_llmtrace_storage(tmp_path):
    llm = ScriptedLLM([_tool_call_turn(), _final_turn()], cost_per_turn=0.01)
    tools = FakeTools()
    agent = Agent(
        llm=llm,
        tools=tools,
        guardrails=Guardrails(max_steps=10),
        trace_log=TraceLog(tmp_path / "t.jsonl"),
    )

    await agent.run("task")

    rows = get_default_storage().query(project=agent.project)
    assert len(rows) == 2
    assert all(row.cost_usd == 0.01 for row in rows)
