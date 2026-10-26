# What this project is, and why it exists

## In one paragraph

`agent-loop` is a small agent that takes a task in plain English, plans and executes it over
several turns, and uses tools to do real things along the way — searching the web, fetching a
page, writing a file. The plan/act/observe loop itself is hand-written: there's no LangChain
`AgentExecutor`, no CrewAI, no framework deciding when to call a tool or when to stop. The tools
it calls are served by a small MCP server this project also builds, so the agent is an MCP
*client* — the same relationship between "model" and "tools" used in real production agent
systems, not a toy function-calling demo.

## Where it sits in the bigger plan

**Project 4 of 5** (`D:\personal\job_applie\projects\open-source-project-plan.md`). It comes
after projects 1-3 for a concrete reason, not just narrative ordering: it reuses tool-calling
and structured-output patterns already exercised in project 2 (RAG Q&A's Claude integration),
and it dogfoods project 3 (`llmtrace`) for cost/latency tracking — building it before project 3
existed would have meant hand-rolling cost tracking here too, then throwing that away once
`llmtrace` existed.

It targets "Agentic AI Engineer" and "Forward Deployed Engineer (AI)" specifically — roles that
ask less about RAG and more about planning, tool use, and the failure modes of autonomous
multi-step execution.

## Why MCP for tools, not plain function-calling (the decision this project made differently)

The portfolio plan's original description just said "function-calling via OpenAI/Anthropic
API." That was deliberately overridden for this project: Revanth's actual production experience
includes building an **MCP server with an OAuth 2.1 authorization server** (Ziply) and a
**clinical-data MCP server** (Tavali, FastMCP) — this is a rarer, more specific skill than
generic tool-calling, and none of projects 1-3 touch MCP at all. Exposing this agent's tools
over a real MCP server (`src/agent_loop/tools/server.py`, `mcp.server.mcpserver.MCPServer`)
instead of inline Anthropic tool schemas means this project actually demonstrates that
production skill, not just "I can write five lines of JSON schema."

## Who it's for

- **A recruiter or interviewer**, skimming the README: a one-command usage example, a concrete
  explanation of why MCP (not just function-calling), and a list of enforced guardrails.
- **An interviewer probing agent design**, deeper: why the step limit is enforced by an
  unbounded loop rather than a capped range, why the cost ceiling reads from `llmtrace`'s own
  storage instead of re-accumulating cost locally, why only the *first* tool call in a turn is
  acted on. All of that lives in this `docs/explained/` folder.
- **Future Revanth**, re-running this before an interview: `agent-loop replay <trace-file>`
  turns any past run back into a readable step-by-step log.

## Honest current status (as of this write-up)

- Code complete. 41 tests pass, including 4 that spawn the real MCP tools server as a
  subprocess (not mocked) and drive real file I/O and a real sandbox-violation attempt through
  it. `ruff check`/`ruff format --check` and `mypy src` are all clean.
- Smoke-tested for real in this session: a scripted multi-turn run made a genuine `web_search`
  call (real results came back from DuckDuckGo) and a genuine `write_file` call through the real
  MCP server, with `llmtrace` tracking real cumulative cost and `agent-loop replay` correctly
  reconstructing the run afterward from its trace file.
- **Not yet true:** this has never been run against a real Anthropic API key on a real,
  non-scripted task. Everything above used a `ScriptedLLM` test double for the model's turns —
  real tool execution, real MCP protocol, fake model responses. Run it once for real, keep that
  trace file, before describing a specific example in an interview.
- **Not yet done:** no git commit, no push, no deployment. CI can't pass yet either — it
  depends on `llmtrace` via a GitHub URL, which doesn't resolve until `llmtrace` is pushed
  first (see that repo's own status note).
