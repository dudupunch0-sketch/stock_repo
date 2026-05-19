from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel


class RunnerResult(BaseModel):
    runner: str
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False


class AgentRunner(Protocol):
    name: str

    def run(self, prompt: str, *, cwd: Path, timeout_seconds: int) -> RunnerResult:
        ...
