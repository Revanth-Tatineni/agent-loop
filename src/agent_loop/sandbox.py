"""Confines the file tools to one workspace directory. A requested path like
"../../.env" or an absolute path outside the workspace resolves outside the sandbox root and
is rejected -- this is what stops an agent that misuses the write_file/read_file tools (by
model error, not malice) from touching anything outside its own workspace.
"""

from __future__ import annotations

from pathlib import Path


class SandboxViolation(Exception):
    """Raised when a requested path resolves outside the sandbox root."""


def resolve_in_sandbox(root: Path, requested_path: str) -> Path:
    root = root.resolve()
    candidate = (root / requested_path).resolve()
    if candidate != root and root not in candidate.parents:
        raise SandboxViolation(f"{requested_path!r} resolves outside the sandbox ({root})")
    return candidate
