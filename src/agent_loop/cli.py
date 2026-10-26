"""`agent-loop run --task "..."` and `agent-loop replay <trace-file>`."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from agent_loop.anthropic_client import AnthropicTurnClient
from agent_loop.guardrails import Guardrails, GuardrailViolation
from agent_loop.loop import Agent
from agent_loop.mcp_client import MCPToolClient
from agent_loop.trace_log import TraceLog
from agent_loop.trace_log import replay as replay_trace


async def _run(args: argparse.Namespace) -> int:
    from anthropic import Anthropic

    guardrails = Guardrails(
        max_steps=args.max_steps,
        cost_ceiling_usd=args.cost_ceiling,
        allowed_tools=set(args.tools.split(",")) if args.tools else None,
    )
    trace_path = Path(args.trace_file)
    llm = AnthropicTurnClient(Anthropic(), model=args.model)

    async with MCPToolClient() as tools:
        agent = Agent(llm=llm, tools=tools, guardrails=guardrails, trace_log=TraceLog(trace_path))
        try:
            answer = await agent.run(args.task)
        except GuardrailViolation as exc:
            print(f"Stopped by a guardrail: {exc}")
            print(f"Trace: {trace_path}")
            return 1

    print(answer)
    print(f"Trace: {trace_path}")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    return asyncio.run(_run(args))


def _cmd_replay(args: argparse.Namespace) -> int:
    print(replay_trace(Path(args.trace_file)))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-loop")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run the agent on a task")
    run.add_argument("--task", required=True)
    run.add_argument("--max-steps", type=int, default=10)
    run.add_argument("--cost-ceiling", type=float, default=0.50)
    run.add_argument(
        "--tools", default=None, help="comma-separated allowlist, e.g. web_search,fetch_url"
    )
    run.add_argument("--model", default="claude-opus-5")
    run.add_argument("--trace-file", default="traces/run.jsonl")
    run.set_defaults(func=_cmd_run)

    replay = sub.add_parser("replay", help="Pretty-print a saved trace file")
    replay.add_argument("trace_file")
    replay.set_defaults(func=_cmd_replay)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
