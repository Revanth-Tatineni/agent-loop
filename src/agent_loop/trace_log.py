"""A replayable, append-only JSON Lines trace of one agent run: one JSON object per step,
written as the run happens (not buffered until the end), so a run that gets stopped by a
guardrail -- or crashes outright -- still leaves a readable trace up to the point it stopped.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Step:
    index: int
    timestamp: float = field(default_factory=time.time)
    thought: str | None = None
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    observation: str | None = None
    cumulative_cost_usd: float = 0.0
    is_final: bool = False
    final_answer: str | None = None
    stopped_reason: str | None = None


class TraceLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, step: Step) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(step)) + "\n")


def load_steps(path: Path) -> list[Step]:
    steps = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                steps.append(Step(**json.loads(line)))
    return steps


def replay(path: Path) -> str:
    lines: list[str] = []
    for step in load_steps(path):
        lines.append(f"--- step {step.index} ---")
        if step.thought:
            lines.append(f"thought: {step.thought}")
        if step.tool_name:
            lines.append(f"tool: {step.tool_name}({step.tool_args})")
        if step.observation:
            lines.append(f"observation: {step.observation}")
        lines.append(f"cumulative cost: ${step.cumulative_cost_usd:.4f}")
        if step.is_final:
            if step.stopped_reason:
                lines.append(f"STOPPED: {step.stopped_reason}")
            else:
                lines.append(f"final answer: {step.final_answer}")
        lines.append("")
    return "\n".join(lines)
