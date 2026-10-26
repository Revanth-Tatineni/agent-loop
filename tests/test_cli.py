from __future__ import annotations

from agent_loop.cli import build_parser
from agent_loop.trace_log import Step, TraceLog


def test_run_command_parses_flags():
    parser = build_parser()
    args = parser.parse_args(
        [
            "run",
            "--task",
            "do x",
            "--max-steps",
            "3",
            "--cost-ceiling",
            "0.1",
            "--tools",
            "web_search,fetch_url",
            "--trace-file",
            "traces/t.jsonl",
        ]
    )
    assert args.task == "do x"
    assert args.max_steps == 3
    assert args.cost_ceiling == 0.1
    assert args.tools == "web_search,fetch_url"
    assert args.func is not None


def test_run_command_defaults():
    parser = build_parser()
    args = parser.parse_args(["run", "--task", "do x"])
    assert args.max_steps == 10
    assert args.cost_ceiling == 0.50
    assert args.tools is None


def test_replay_command_prints_trace(tmp_path, capsys):
    trace_path = tmp_path / "run.jsonl"
    TraceLog(trace_path).record(Step(index=1, is_final=True, final_answer="ok"))

    parser = build_parser()
    args = parser.parse_args(["replay", str(trace_path)])
    exit_code = args.func(args)

    assert exit_code == 0
    assert "final answer: ok" in capsys.readouterr().out
