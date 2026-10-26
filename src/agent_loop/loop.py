"""The hand-rolled ReAct loop: ask the model what to do, run the tool it picked, feed the
result back, repeat -- until the model stops calling tools, or a guardrail trips. The step
limit is the *only* thing bounding the loop below (`itertools.count(1)`, not a bounded range),
so the guardrail is actually load-bearing, not a decorative check backed up by Python doing
the real work.
"""

from __future__ import annotations

import itertools
import uuid
from typing import Any, Protocol

from llmtrace import get_default_storage

from agent_loop.anthropic_client import LLMTurn
from agent_loop.guardrails import Guardrails, GuardrailViolation
from agent_loop.trace_log import Step, TraceLog


class ToolExecutor(Protocol):
    def tool_schemas(self, allowed: set[str] | None = None) -> list[dict[str, Any]]: ...
    async def call(self, name: str, arguments: dict[str, Any]) -> str: ...


class Agent:
    def __init__(
        self,
        *,
        llm: LLMTurn,
        tools: ToolExecutor,
        guardrails: Guardrails,
        trace_log: TraceLog,
        project_prefix: str = "agent-loop",
    ) -> None:
        self.llm = llm
        self.tools = tools
        self.guardrails = guardrails
        self.trace_log = trace_log
        self.project = f"{project_prefix}:{uuid.uuid4().hex[:8]}"

    def _cumulative_cost(self) -> float:
        return float(get_default_storage().summary(project=self.project)["total_cost_usd"])

    def _record_stop(self, step_index: int, exc: GuardrailViolation, cost: float) -> None:
        self.trace_log.record(
            Step(
                index=step_index,
                cumulative_cost_usd=cost,
                is_final=True,
                stopped_reason=f"{type(exc).__name__}: {exc}",
            )
        )

    async def run(self, task: str) -> str:
        messages: list[dict[str, Any]] = [{"role": "user", "content": task}]
        tool_schemas = self.tools.tool_schemas(self.guardrails.allowed_tools)

        for step_index in itertools.count(1):
            try:
                self.guardrails.check_step(step_index)
            except GuardrailViolation as exc:
                self._record_stop(step_index, exc, self._cumulative_cost())
                raise

            turn = self.llm.turn(messages, tool_schemas, project=self.project)
            cost = self._cumulative_cost()

            try:
                self.guardrails.check_cost(cost)
                if turn.tool_call is not None:
                    self.guardrails.check_tool_allowed(turn.tool_call.name)
            except GuardrailViolation as exc:
                self._record_stop(step_index, exc, cost)
                raise

            if turn.tool_call is None:
                self.trace_log.record(
                    Step(
                        index=step_index,
                        thought=turn.text,
                        cumulative_cost_usd=cost,
                        is_final=True,
                        final_answer=turn.text,
                    )
                )
                return turn.text or ""

            messages.append({"role": "assistant", "content": turn.raw_content})
            observation = await self.tools.call(turn.tool_call.name, turn.tool_call.arguments)
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": turn.tool_call.id,
                            "content": observation,
                        }
                    ],
                }
            )

            self.trace_log.record(
                Step(
                    index=step_index,
                    thought=turn.text,
                    tool_name=turn.tool_call.name,
                    tool_args=turn.tool_call.arguments,
                    observation=observation,
                    cumulative_cost_usd=cost,
                )
            )

        raise AssertionError("unreachable: itertools.count(1) never stops on its own")
