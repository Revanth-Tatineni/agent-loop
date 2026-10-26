# How a run actually flows

## 1. Starting a run

`cli.py`'s `_run` builds a `Guardrails` from CLI flags, an `AnthropicTurnClient` (real Anthropic
SDK client + model name), and opens an `MCPToolClient` as an async context manager -- which
spawns `python -m agent_loop.tools.server` as a subprocess and performs the MCP handshake
(`initialize()`, then `list_tools()`) before the `with` block's body runs. An `Agent` is built
from all three, plus a `TraceLog` pointed at the run's trace file, and `agent.run(task)` is
awaited.

## 2. One step of the loop

```
Agent.run(task):
    messages = [{"role": "user", "content": task}]
    tool_schemas = self.tools.tool_schemas(guardrails.allowed_tools)   # fetched once, not per step

    for step_index in itertools.count(1):
        guardrails.check_step(step_index)              # the ONLY thing that can end this loop
                                                          # without the model finishing
        turn = self.llm.turn(messages, tool_schemas, project=self.project)   # <- real LLM call,
                                                                               #    traced by llmtrace
        cost = self._cumulative_cost()                  # reads llmtrace's own storage

        guardrails.check_cost(cost)
        if turn.tool_call is not None:
            guardrails.check_tool_allowed(turn.tool_call.name)

        if turn.tool_call is None:
            trace_log.record(Step(..., is_final=True, final_answer=turn.text))
            return turn.text

        messages.append({"role": "assistant", "content": turn.raw_content})
        observation = await self.tools.call(turn.tool_call.name, turn.tool_call.arguments)
        messages.append({"role": "user", "content": [{"type": "tool_result",
                                                         "tool_use_id": turn.tool_call.id,
                                                         "content": observation}]})
        trace_log.record(Step(..., tool_name=..., tool_args=..., observation=observation))
```

Every guardrail check is a `try`/`except GuardrailViolation` in the real code (see
`loop.py`) -- simplified above to show the order: step limit is checked *before* the LLM call
(so an about-to-be-rejected step never spends a token), cost and tool-allowlist are checked
*after* the LLM call but *before* the tool runs (so a disallowed or too-expensive tool call
never actually executes).

## 3. When a guardrail trips

`Agent._record_stop(step_index, exc, cost)` writes one final `Step` to the trace log with
`is_final=True` and `stopped_reason=f"{type(exc).__name__}: {exc}"`, then the same exception is
re-raised out of `run()`. `cli.py`'s `_run` catches `GuardrailViolation`, prints "Stopped by a
guardrail: ..." and the trace file path, and returns exit code 1 -- a tripped guardrail is a
controlled stop, not a crash, and the trace file always says exactly why.

## 4. Discovering and calling a tool, through MCP

```
MCPToolClient.connect():
    stdio_client(StdioServerParameters(command=sys.executable, args=["-m", "agent_loop.tools.server"]))
        -> spawns the subprocess, wires up its stdin/stdout as the transport
    ClientSession(read, write).initialize()
        -> the MCP handshake
    session.list_tools()
        -> {name: {"name", "description", "input_schema"}} for each of the 4 tools,
           stored in self._tools

MCPToolClient.call(name, arguments):
    session.call_tool(name, arguments)
        -> sent over stdio to the subprocess; MCPServer's @mcp.tool()-decorated function runs
           inside the subprocess, in a worker thread (anyio.to_thread.run_sync, since these
           are plain sync functions)
        -> result.content: a list of content blocks; text blocks are joined
        -> result.is_error: if true, the text comes back prefixed "ERROR: " instead of raising
```

The last point matters for the loop: a tool failure (a missing file, a blocked sandbox path) is
turned into a plain string observation the model can read and react to (e.g. try a different
path), not a Python exception that would crash the whole run. `SandboxViolation` raised inside
`write_file`/`read_file` is exactly this case -- it surfaces to the agent as
`"ERROR: '../escape.txt' resolves outside the sandbox (...)"`, not as a stack trace.

## 5. Replaying a finished run

`agent-loop replay <trace-file>` just calls `trace_log.replay(path)`: read every JSON line back
into a `Step`, and print each one's thought / tool call+args / observation / running cost, in
order, ending with either the final answer or the guardrail that stopped it. Nothing about
replay re-executes anything -- it's a pure read of what already happened, which is exactly what
makes a stopped or finished run inspectable after the process has exited.
