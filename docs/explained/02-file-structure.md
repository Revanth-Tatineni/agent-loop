# File structure, and why it's shaped this way

## The tree

```
agent-loop/
├── pyproject.toml              hatchling build, deps incl. llmtrace (git URL), ruff/mypy/pytest config
├── README.md
├── .gitignore
├── src/agent_loop/
│   ├── __init__.py
│   ├── cli.py                   `agent-loop run`, `agent-loop replay`
│   ├── loop.py                   Agent -- the hand-rolled ReAct loop
│   ├── anthropic_client.py      AnthropicTurnClient, TurnResult, ToolCall, _parse_turn
│   ├── mcp_client.py            MCPToolClient -- the agent's MCP client
│   ├── guardrails.py            Guardrails, StepLimitExceeded, CostLimitExceeded, ToolNotAllowed
│   ├── trace_log.py             Step, TraceLog, load_steps(), replay()
│   ├── sandbox.py               resolve_in_sandbox(), SandboxViolation
│   └── tools/
│       ├── __init__.py
│       ├── server.py             the MCP server: web_search, fetch_url, write_file, read_file
│       ├── search.py            duckduckgo_search() -- pure logic, no MCP
│       ├── fetch.py             fetch_text() -- pure logic, no MCP
│       └── files.py             write_sandboxed_file(), read_sandboxed_file() -- pure logic
├── tests/
│   ├── conftest.py              isolated llmtrace storage per test
│   ├── test_sandbox.py
│   ├── test_files_tool.py
│   ├── test_search_tool.py
│   ├── test_fetch_tool.py
│   ├── test_guardrails.py
│   ├── test_trace_log.py
│   ├── test_anthropic_client.py
│   ├── test_loop.py             the ReAct loop, with ScriptedLLM + FakeTools
│   ├── test_mcp_integration.py  the ONLY tests that spawn the real MCP server subprocess
│   └── test_cli.py
└── .github/workflows/ci.yml
```

## Why `tools/server.py` is thin, and the actual logic lives in `search.py`/`fetch.py`/`files.py`

Every `@mcp.tool()`-decorated function in `server.py` is one line: call the matching plain
function in `search.py`, `fetch.py` or `files.py`. This split exists so the *logic* (how
DuckDuckGo's HTML is parsed, how a path is confined to the sandbox) can be unit-tested directly
— fast, no subprocess, no MCP protocol overhead — while a *separate*, smaller set of tests
(`test_mcp_integration.py`) proves the MCP wiring around that logic actually works. Without the
split, every test of the parsing logic would have to go through a real MCP subprocess, making
the whole suite slower and the parsing bugs harder to isolate from protocol bugs.

## Why `anthropic_client.py` and `mcp_client.py` are separate files, not one "clients" module

They wrap two unrelated things — the LLM API and the tools protocol — and nothing in one needs
to know the other exists. `loop.py`'s `Agent` depends on both only through the `LLMTurn` and
`ToolExecutor` protocols (see `01-architecture.md`), never on their concrete classes directly.

## Why `test_mcp_integration.py` is its own file, not folded into `test_search_tool.py` etc.

It's the one file in the whole test suite that spawns a real subprocess and talks real stdio
JSON-RPC — meaningfully slower and more failure-prone (a hung process, a port/stdio issue) than
every other test file, which runs in-process against fakes or `tmp_path`. Keeping it separate
makes it easy to see, at a glance, which 4 of the 41 tests are the "real" integration tests and
which 37 are fast unit tests.

## Why there's no `services/`/`repositories/` layering like projects 1/2

Same reasoning as `llmtrace` (project 3): there's no HTTP boundary, no multi-tenant database, no
request lifecycle here. The files are organized by *what they depend on*, not by a web-service
layering convention that doesn't apply:

```
sandbox.py, tools/search.py, tools/fetch.py, tools/files.py   (no dependencies on each other)
    ^
tools/server.py          (depends on all four of the above, via MCP decorators)
    ^
mcp_client.py             (depends on nothing in this package -- just the mcp SDK)
guardrails.py             (depends on nothing in this package)
trace_log.py              (depends on nothing in this package)
anthropic_client.py       (depends on llmtrace, not on anything else here)
    ^
loop.py                   (depends on anthropic_client, guardrails, trace_log, llmtrace)
    ^
cli.py                    (depends on everything -- it's the one place all the pieces meet)
```
