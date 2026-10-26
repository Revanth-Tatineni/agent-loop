from __future__ import annotations

import pytest

from agent_loop.sandbox import SandboxViolation, resolve_in_sandbox


def test_relative_path_inside_sandbox_resolves(tmp_path):
    resolved = resolve_in_sandbox(tmp_path, "notes/summary.md")
    assert resolved == (tmp_path / "notes" / "summary.md").resolve()


def test_parent_traversal_is_blocked(tmp_path):
    with pytest.raises(SandboxViolation):
        resolve_in_sandbox(tmp_path, "../../etc/passwd")


def test_absolute_path_outside_sandbox_is_blocked(tmp_path, monkeypatch):
    outside = tmp_path.parent / "outside.txt"
    with pytest.raises(SandboxViolation):
        resolve_in_sandbox(tmp_path, str(outside))


def test_sandbox_root_itself_is_allowed(tmp_path):
    assert resolve_in_sandbox(tmp_path, ".") == tmp_path.resolve()
