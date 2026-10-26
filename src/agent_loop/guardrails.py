"""The three guardrails: a step limit, a dollar cost ceiling, and a tool allowlist. Each is a
plain check that raises a specific GuardrailViolation subclass -- loop.py is the only thing
that catches these, and it catches the base class, so adding a fourth guardrail later doesn't
require touching the loop's except clause.
"""

from __future__ import annotations

from dataclasses import dataclass


class GuardrailViolation(Exception):
    """Base class for every guardrail trip."""


class StepLimitExceeded(GuardrailViolation):
    pass


class CostLimitExceeded(GuardrailViolation):
    pass


class ToolNotAllowed(GuardrailViolation):
    pass


@dataclass
class Guardrails:
    max_steps: int = 10
    cost_ceiling_usd: float = 0.50
    allowed_tools: set[str] | None = None  # None = every discovered tool is allowed

    def check_step(self, step_index: int) -> None:
        if step_index > self.max_steps:
            raise StepLimitExceeded(f"step {step_index} exceeds max_steps={self.max_steps}")

    def check_cost(self, cumulative_cost_usd: float) -> None:
        if cumulative_cost_usd > self.cost_ceiling_usd:
            raise CostLimitExceeded(
                f"cumulative cost ${cumulative_cost_usd:.4f} exceeds "
                f"cost_ceiling_usd=${self.cost_ceiling_usd:.4f}"
            )

    def check_tool_allowed(self, tool_name: str) -> None:
        if self.allowed_tools is not None and tool_name not in self.allowed_tools:
            raise ToolNotAllowed(f"{tool_name!r} is not in the allowed tool set")
