# Code and logic, file by file

## `sandbox.py`

```python
def resolve_in_sandbox(root: Path, requested_path: str) -> Path:
    root = root.resolve()
    candidate = (root / requested_path).resolve()
    if candidate != root and root not in candidate.parents:
        raise SandboxViolation(...)
    return candidate
```

`root / requested_path` handles both attack shapes without separate logic: if `requested_path`
is `"../../etc/passwd"`, the combined path resolves (via `.resolve()`, which collapses `..`
segments) to somewhere outside `root`, caught by the `parents` check. If `requested_path` is
itself an *absolute* path (e.g. `C:\Users\...\outside.txt`), Python's `Path.__truediv__`
discards `root` entirely and `candidate` becomes that absolute path directly -- which also
isn't under `root`, so the same single check still catches it. One check, two attack shapes,
verified by `test_sandbox.py`'s `test_parent_traversal_is_blocked` and
`test_absolute_path_outside_sandbox_is_blocked`.

## `tools/search.py` and `tools/fetch.py`

Both take an optional `client: httpx.Client | None` and create their own
(`client = client or httpx.Client(...)`) only when the caller didn't supply one, closing it in
a `finally` only if they created it (`owns_client`). This is what lets
`test_search_tool.py`/`test_fetch_tool.py` inject an `httpx.Client(transport=httpx.MockTransport(...))`
with a fixed HTML response, so the parsing logic is tested deterministically with zero real
network calls, while the real server code (`server.py`) calls them with no client argument and
gets a real one.

`search.py`'s `_parse_results` walks `soup.select("a.result__a")` and, for each link, looks up
its enclosing `div.result__body` to find the matching `.result__snippet` -- this two-step
lookup (link, then its parent's snippet) exists because DuckDuckGo's HTML puts the title link
and the snippet as siblings inside one result container, not inside each other.
`test_malformed_html_returns_empty_list_not_an_exception` is the test that protects the
"degrade gracefully" decision from `01-architecture.md`'s reasoning: if DuckDuckGo changes its
markup, `soup.select(...)` just returns an empty list, no exception, no crashed tool call.

## `tools/files.py` and `tools/server.py`

`write_sandboxed_file`/`read_sandboxed_file` do exactly one thing each beyond the sandbox check:
`target.parent.mkdir(parents=True, exist_ok=True)` before writing (so a write into a new
subdirectory doesn't fail with "no such directory"), and `target.is_file()` before reading (so
a missing file raises a clear `FileNotFoundError` instead of whatever `read_text()` would raise
on a missing path). `server.py`'s four `@mcp.tool()` functions each call exactly one of these
plain functions and return its result -- the docstring on each decorated function *is* the
schema description the model sees when deciding whether to call that tool, which is why they're
written as instructions ("Fetch a URL and return its visible text content, truncated to
max_chars") rather than implementation notes.

## `guardrails.py`

```python
class GuardrailViolation(Exception): ...
class StepLimitExceeded(GuardrailViolation): ...
class CostLimitExceeded(GuardrailViolation): ...
class ToolNotAllowed(GuardrailViolation): ...
```

Three leaf exceptions, one shared base. `loop.py` catches only `GuardrailViolation` -- it never
needs to know which specific guardrail tripped to do the right thing (stop, record, re-raise);
only `cli.py`'s error message and the trace log's `stopped_reason` field (via
`type(exc).__name__`) care which one it was. Adding a fifth guardrail later means adding one
more leaf class and one more `check_*` method; `loop.py`'s `except GuardrailViolation` doesn't
change.

## `trace_log.py`

```python
def record(self, step: Step) -> None:
    with self.path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(step)) + "\n")
```

Opens, appends one line, and closes the file on *every single step* -- not once at the start of
the run, kept open throughout. This is slower (a syscall per step instead of per run) but means
a process that's killed mid-run (by the OS, by the user, by a crash this code didn't predict)
still leaves every step up to that point readable in the `.jsonl` file. `load_steps` reads it
back by splitting on newlines and `json.loads`-ing each one independently, which is also why a
`.jsonl` file (one JSON object per line) was chosen over one big JSON array -- a half-written
JSON array is invalid and unparseable; a half-written `.jsonl` file is just a shorter, still
valid sequence of complete lines.

## `anthropic_client.py`

```python
def _parse_turn(response: Any) -> TurnResult:
    for block in response.content:
        if block.type == "text":
            ...
        elif block.type == "tool_use":
            if tool_call is None:   # only the first tool call in a turn is acted on
                tool_call = ToolCall(...)
```

Iterates `response.content` once, branching on `block.type`. Text blocks accumulate into
`text_parts` (joined with spaces at the end); only the *first* `tool_use` block becomes the
`ToolCall` that `loop.py` will act on, but every block -- text and every tool_use, including
ones that won't be executed -- is preserved in `raw_content`, because `raw_content` becomes the
assistant message appended back into the conversation, and that message has to faithfully
represent what the model actually said, not just the part this agent chose to act on.

```python
def turn(self, messages, tool_schemas, *, project):
    with trace_call(provider="anthropic", model=self.model, operation="agent.turn", project=project) as t:
        response = self.client.messages.create(model=self.model, max_tokens=1024,
                                                 messages=messages, tools=tool_schemas)
        t.record_response(response)
        return _parse_turn(response)
```

`trace_call`'s `with` block wraps the real network call; `t.record_response(response)` is
`llmtrace`'s extractor pulling `response.usage.input_tokens`/`output_tokens` off the real
Anthropic SDK response object, the same mechanism `test_anthropic_client.py`'s
`test_anthropic_turn_client_records_cost_and_tokens_via_llmtrace` verifies end to end: a fake
client stands in for the network call, but the `llmtrace` recording and cost calculation that
follows are real, unmocked code.

## `loop.py`

Already walked in detail in `01-architecture.md` (why `itertools.count`, why cost reads from
`llmtrace`'s storage) and `03-flow.md` (the step-by-step order of checks). The one thing worth
adding here: `_cumulative_cost()` is called *twice* per step in the worst case -- once after the
LLM turn (to check the cost ceiling) and, if a guardrail trips at the *step* check instead, once
more in `_record_stop`'s caller. Both calls are cheap aggregate SQL queries against a local
SQLite file, not network calls, so the duplication was an acceptable simplicity trade rather
than something worth threading a cached value through for.

## `mcp_client.py`

```python
async def connect(self) -> None:
    params = StdioServerParameters(command=self._command, args=self._args, env=self._env)
    read, write = await self._stack.enter_async_context(stdio_client(params))
    self._session = await self._stack.enter_async_context(ClientSession(read, write))
    await self._session.initialize()
    result = await self._session.list_tools()
    self._tools = {tool.name: {...} for tool in result.tools}
```

Uses one `AsyncExitStack` to hold both the `stdio_client` transport and the `ClientSession`, so
`close()` is a single `await self._stack.aclose()` that unwinds both in the right order,
regardless of how many context managers end up nested here. `tool_schemas(allowed)` builds the
Anthropic-format list from `self._tools` filtered to an allowlist -- this is a different,
narrower filter than `guardrails.check_tool_allowed`: this one controls what the *model even
sees* as available (so it can't try to call a tool it was never offered), while the guardrail
is a second, independent check for *if* the model somehow produces a disallowed tool-use block
anyway. Belt and suspenders here was intentional, unlike the `range()`/`itertools.count`
decision above -- the model choosing from a restricted tool list is a UX/cost optimization
(fewer tokens spent describing tools it can't use), not the actual safety boundary; the
guardrail is.

## Testing strategy

Like projects 1-3, nothing is tested against a mocked database or a mocked model where a real
one could be used cheaply: `test_mcp_integration.py` spawns the actual `tools/server.py`
subprocess and speaks real MCP to it (no network calls inside it, so it's fast and
deterministic); `test_anthropic_client.py` fakes only the Anthropic SDK client object (a
network call is the one thing that genuinely can't run in CI without a paid key) while letting
`llmtrace` do real, unmocked recording. `test_loop.py`'s `ScriptedLLM` and `FakeTools` are the
only pure test doubles in the suite, and they exist because the *loop's* own logic (guardrail
ordering, trace recording, message history construction) is what's under test there, not the
LLM or the tools behind it.
