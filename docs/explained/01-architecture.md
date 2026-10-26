# Architecture decisions, and the alternatives that were rejected

## MCP server for tools, not inline Anthropic tool schemas

**Chosen:** `tools/server.py` is a real `MCPServer` (the official `mcp` SDK); the agent connects
to it as an `MCPToolClient` (an MCP client over stdio), discovers tools via `list_tools()`, and
calls them via `call_tool()`.

**Rejected:** defining tools inline as plain dicts passed straight to
`anthropic.messages.create(tools=...)`, with Python functions called directly by name.

**Why:** see `00-overview.md` — this is the one place this project deliberately diverges from
the portfolio plan's original text, specifically to showcase MCP. The practical cost is real:
every tool call now goes through a subprocess and a JSON-RPC-like protocol instead of a direct
function call, which is slower and has more failure surface (a crashed subprocess, a malformed
schema) than calling a Python function. That cost is accepted because the point of this project
is to demonstrate the MCP pattern, not to minimize latency.

## `itertools.count(1)`, not `range(1, max_steps + 1)`

**Chosen:** the loop in `loop.py` iterates an unbounded counter and relies entirely on
`guardrails.check_step(step_index)` to stop it.

**Rejected:** a bounded `for step_index in range(1, max_steps + 1):`, with the guardrail check
left in as a "belt and suspenders" extra.

**Why:** the README's claim is "guardrails, enforced, not just described." If `range()` were
already bounding the loop, the step-limit guardrail would be decorative — it would never
actually be the thing that stops an infinite loop, `range()` would. Using an unbounded counter
makes the guardrail load-bearing, and `test_loop.py`'s
`test_step_limit_guardrail_actually_stops_an_agent_that_never_finishes` genuinely tests that the
guardrail (not Python's range implementation) is what stops execution.

## The cost-ceiling guardrail reads from `llmtrace`'s storage, not a local running total

**Chosen:** `Agent._cumulative_cost()` calls `get_default_storage().summary(project=self.project)`
— the same `llmtrace` storage every traced call already writes to — rather than the agent
keeping its own running `total_cost += turn.cost` variable.

**Why:** this is the actual dogfooding, not just an import statement. If the agent tracked cost
itself, `llmtrace` would just be a logging side-channel the guardrail never actually reads —
the guardrail and the observability tool would tell two independently-computed stories that
could drift apart. Reading the guardrail's number from the same place the dashboard reads
means there's only one source of truth for "how much has this run cost," and it's the one
project 3 was built to own. The cost this design accepts: one extra SQL query per step (a
`summary()` aggregate), which is negligible next to an LLM API round trip.

## Only the first tool call in a turn is acted on

**Chosen:** `anthropic_client._parse_turn` scans a response's content blocks and keeps the
*first* `tool_use` block as `TurnResult.tool_call`; any additional tool-use blocks in the same
turn are parsed into `raw_content` (so the message history stays faithful) but never executed.

**Rejected:** executing every tool call in a turn, in parallel or in sequence.

**Why:** a ReAct loop that's meant to be replayable and easy to explain in an interview is
simpler with one decision per step: one thought, one action, one observation. Parallel tool
execution is a real pattern in production agents, but it also means the guardrails (step
count, cost, trace log) would all need to reason about *sets* of calls per step instead of one
— a meaningfully bigger design, documented here as explicitly out of scope rather than silently
unsupported.

## A `ToolExecutor`/`LLMTurn` `Protocol`, not a concrete base class

**Chosen:** `loop.py`'s `Agent` depends on two `typing.Protocol` interfaces
(`ToolExecutor`, `LLMTurn`), not concrete classes.

**Why:** this is what makes `test_loop.py` possible without a real Anthropic API key or a real
MCP subprocess — `ScriptedLLM` and `FakeTools` satisfy the protocols structurally (duck typing
checked by mypy) without inheriting from anything. The real `AnthropicTurnClient` and
`MCPToolClient` satisfy the same protocols. This mirrors project 2's `Providers`/fake-injection
testing pattern, applied to an agent loop instead of a FastAPI service.

## `argparse`, direct `python -m agent_loop.tools.server` subprocess, no process manager

The MCP tools server is spawned directly as a subprocess by `MCPToolClient` using
`sys.executable -m agent_loop.tools.server` — no Docker, no supervisor process, no health
check loop. For a single-agent, single-user CLI tool, the tools server's lifetime is exactly
the agent run's lifetime; adding process-management infrastructure here would be solving a
problem (a long-running, multi-client tools server) this project doesn't have.
