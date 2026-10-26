from __future__ import annotations

import pytest
from llmtrace import configure


@pytest.fixture(autouse=True)
def _isolated_llmtrace_storage(tmp_path, monkeypatch):
    """Every test gets its own llmtrace database, so cost-ceiling tests never see cost left
    over from a previous test or a real llmtrace.db sitting in the working directory."""
    db_path = tmp_path / "llmtrace.db"
    monkeypatch.setenv("LLMTRACE_DB_URL", f"sqlite:///{db_path}")
    configure()
    yield
