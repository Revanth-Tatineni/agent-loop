# agent-loop

[![CI](https://github.com/Revanth-Tatineni/agent-loop/actions/workflows/ci.yml/badge.svg)](https://github.com/Revanth-Tatineni/agent-loop/actions/workflows/ci.yml)

A small agent that plans and executes multi-step tasks using tools, with the ReAct loop
(plan → act → observe) hand-written rather than imported from an agent framework. Its tools —
web search, page fetch, sandboxed file read/write — are served by a small **MCP server**, and
the agent is an MCP client calling them, the same pattern used in production MCP work (not
plain hand-rolled function-calling schemas).

```bash
agent-loop run --task "Research Anthropic and save a one-paragraph summary to summary.md" \
               --max-steps 10 --cost-ceiling 0.50 --tools web_search,fetch_url,write_file
```

## Why this exists

Project 4 of a 5-project portfolio. It targets "Agentic AI Engineer" and "Forward Deployed
Engineer (AI)" roles specifically, and deliberately builds the ReAct loop itself (reading tool
calls off the raw Anthropic API response, executing them, feeding results back) before reaching
for a framework — the point is to be able to explain exactly what happens on every turn, not to
assemble a black box.

## What makes this one different from a plain tool-calling demo

- **Tools are served over MCP, not just native function-calling schemas.** `tools/server.py`
  is a real MCP server (`mcp.server.mcpserver.MCPServer`); the agent discovers its tools via
  `list_tools()` and calls them via `call_tool()`, converting MCP's tool schema into Anthropic's
  tool-use format at the boundary. This mirrors how MCP is actually used in production agent
  systems, not a toy.
- **Guardrails, enforced, not just described:** a step limit, a dollar cost ceiling, and a tool
  allowlist. The step limit is the *only* thing bounding the loop (it runs on an unbounded
  counter, not a capped range) — each guardrail has a test that deliberately trips it. See
  `docs/explained/` for the design reasoning.
- **A replayable JSON trace log.** Every step (the model's reasoning text, which tool it called,
  with what arguments, what came back, and the running cost) is appended to a `.jsonl` file.
  `agent-loop replay <file>` plays it back step by step — this is what makes a run debuggable
  after the fact instead of only during.
- **Dogfoods project 3.** Every call to Claude goes through `llmtrace`'s `trace_call`, tagged
  with a per-run project id. The cost-ceiling guardrail doesn't recompute cost itself — it reads
  the running total straight out of `llmtrace`'s own storage.

## Stack

Python, the official `mcp` SDK (`MCPServer` + `ClientSession`, stdio transport), the Anthropic
SDK (tool use), `httpx` + BeautifulSoup for the web tools, `llmtrace` (project 3) for
cost/latency tracking, pytest, ruff, mypy, GitHub Actions.

## Status

- Code complete: 41 tests pass, including 4 that spawn the real MCP tools server as a
  subprocess (not mocked) to prove the MCP wiring itself works — file read/write and sandbox
  rejection, exercised through the real protocol. `ruff check`/`format --check` and `mypy src`
  are clean.
- Smoke-tested end to end in this session: a scripted multi-turn run drove a real `web_search`
  call (real DuckDuckGo results) and a real `write_file` call through the real MCP server, with
  `llmtrace` tracking real cumulative cost and `agent-loop replay` correctly reconstructing the
  run from its trace file.
- **Not yet done:** no git commit, no push to GitHub, no deployment. CI can't go green yet
  either — it depends on `llmtrace` via a GitHub URL (see `pyproject.toml`), so `llmtrace` has
  to be pushed first.
- **Not yet true:** this hasn't been run against a real Anthropic API key for a full, non-
  scripted task — the loop, guardrails and MCP integration are verified with a scripted LLM and
  a real tools server, not a live model. Do that run once and keep the trace before putting a
  specific example in this README.
