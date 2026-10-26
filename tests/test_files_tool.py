from __future__ import annotations

import pytest

from agent_loop.sandbox import SandboxViolation
from agent_loop.tools.files import read_sandboxed_file, write_sandboxed_file


def test_write_then_read_round_trip(tmp_path):
    write_sandboxed_file(tmp_path, "notes/a.txt", "hello world")
    assert read_sandboxed_file(tmp_path, "notes/a.txt") == "hello world"


def test_write_creates_parent_directories(tmp_path):
    write_sandboxed_file(tmp_path, "a/b/c/d.txt", "deep")
    assert (tmp_path / "a" / "b" / "c" / "d.txt").read_text() == "deep"


def test_read_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_sandboxed_file(tmp_path, "does-not-exist.txt")


def test_write_outside_sandbox_is_blocked(tmp_path):
    with pytest.raises(SandboxViolation):
        write_sandboxed_file(tmp_path, "../escape.txt", "no")
