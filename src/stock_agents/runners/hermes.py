from __future__ import annotations

import subprocess
import time
from pathlib import Path

from stock_agents.runners.base import RunnerResult


class HermesRunner:
    name = "hermes"

    def __init__(self, *, executable: str = "hermes", provider: str | None = None, model: str | None = None) -> None:
        self.executable = executable
        self.provider = provider
        self.model = model

    def build_command(self, prompt: str) -> list[str]:
        command = [self.executable, "chat", "-Q"]
        if self.provider:
            command.extend(["--provider", self.provider])
        if self.model:
            command.extend(["-m", self.model])
        command.extend(["-q", prompt, "--source", "stock-agents"])
        return command

    def run(self, prompt: str, *, cwd: Path, timeout_seconds: int) -> RunnerResult:
        started = time.monotonic()
        command = self.build_command(prompt)
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            return RunnerResult(
                runner=self.name,
                command=command,
                exit_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                duration_seconds=time.monotonic() - started,
                timed_out=False,
            )
        except OSError as exc:
            return RunnerResult(
                runner=self.name,
                command=command,
                exit_code=127,
                stdout="",
                stderr=f"Hermes executable not found or could not be executed: {exc}",
                duration_seconds=time.monotonic() - started,
                timed_out=False,
            )
        except subprocess.TimeoutExpired as exc:
            return RunnerResult(
                runner=self.name,
                command=command,
                exit_code=124,
                stdout=_coerce_output(exc.stdout),
                stderr=_coerce_output(exc.stderr) or f"Hermes runner timed out after {timeout_seconds} seconds.",
                duration_seconds=time.monotonic() - started,
                timed_out=True,
            )


def _coerce_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value
