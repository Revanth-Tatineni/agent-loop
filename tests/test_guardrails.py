from __future__ import annotations

import pytest

from agent_loop.guardrails import (
    CostLimitExceeded,
    Guardrails,
    StepLimitExceeded,
    ToolNotAllowed,
)


def test_step_within_limit_does_not_raise():
    Guardrails(max_steps=5).check_step(5)


def test_step_beyond_limit_raises():
    with pytest.raises(StepLimitExceeded):
        Guardrails(max_steps=5).check_step(6)


def test_cost_within_ceiling_does_not_raise():
    Guardrails(cost_ceiling_usd=1.0).check_cost(0.99)


def test_cost_beyond_ceiling_raises():
    with pytest.raises(CostLimitExceeded):
        Guardrails(cost_ceiling_usd=1.0).check_cost(1.01)


def test_no_allowlist_means_every_tool_is_allowed():
    Guardrails(allowed_tools=None).check_tool_allowed("anything")


def test_tool_outside_allowlist_raises():
    with pytest.raises(ToolNotAllowed):
        Guardrails(allowed_tools={"web_search"}).check_tool_allowed("write_file")


def test_tool_inside_allowlist_does_not_raise():
    Guardrails(allowed_tools={"web_search", "write_file"}).check_tool_allowed("write_file")
