"""The two file tools. Both go through sandbox.resolve_in_sandbox first -- neither function
below does its own path-safety checking, on purpose, so there's exactly one place that logic
can be wrong.
"""

from __future__ import annotations

from pathlib import Path

from agent_loop.sandbox import resolve_in_sandbox


def write_sandboxed_file(root: Path, path: str, content: str) -> str:
    target = resolve_in_sandbox(root, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"wrote {len(content)} characters to {target.relative_to(root)}"


def read_sandboxed_file(root: Path, path: str) -> str:
    target = resolve_in_sandbox(root, path)
    if not target.is_file():
        raise FileNotFoundError(f"{path} does not exist in the sandbox")
    return target.read_text(encoding="utf-8")
