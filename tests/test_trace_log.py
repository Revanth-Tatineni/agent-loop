from __future__ import annotations

from agent_loop.trace_log import Step, TraceLog, load_steps, replay


def test_record_then_load_round_trips(tmp_path):
    log = TraceLog(tmp_path / "run.jsonl")
    log.record(Step(index=1, thought="t1", tool_name="web_search", tool_args={"query": "x"}))
    log.record(Step(index=2, is_final=True, final_answer="done"))

    steps = load_steps(tmp_path / "run.jsonl")
    assert len(steps) == 2
    assert steps[0].tool_name == "web_search"
    assert steps[1].is_final is True
    assert steps[1].final_answer == "done"


def test_record_appends_not_overwrites(tmp_path):
    log = TraceLog(tmp_path / "run.jsonl")
    log.record(Step(index=1))
    log.record(Step(index=2))
    assert len(load_steps(tmp_path / "run.jsonl")) == 2


def test_creates_parent_directory(tmp_path):
    log = TraceLog(tmp_path / "nested" / "run.jsonl")
    log.record(Step(index=1))
    assert (tmp_path / "nested" / "run.jsonl").exists()


def test_replay_renders_tool_step_and_final_step(tmp_path):
    path = tmp_path / "run.jsonl"
    log = TraceLog(path)
    log.record(
        Step(
            index=1,
            thought="searching",
            tool_name="web_search",
            tool_args={"query": "x"},
            observation="found it",
            cumulative_cost_usd=0.01,
        )
    )
    log.record(
        Step(index=2, is_final=True, final_answer="The answer is x", cumulative_cost_usd=0.02)
    )

    output = replay(path)
    assert "tool: web_search({'query': 'x'})" in output
    assert "observation: found it" in output
    assert "final answer: The answer is x" in output


def test_replay_renders_guardrail_stop(tmp_path):
    path = tmp_path / "run.jsonl"
    log = TraceLog(path)
    log.record(
        Step(
            index=11,
            is_final=True,
            cumulative_cost_usd=0.05,
            stopped_reason="StepLimitExceeded: step 11 exceeds max_steps=10",
        )
    )

    output = replay(path)
    assert "STOPPED: StepLimitExceeded: step 11 exceeds max_steps=10" in output
