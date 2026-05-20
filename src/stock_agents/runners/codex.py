from __future__ import annotations

import subprocess
import time
from pathlib import Path

from stock_agents.runners.base import RunnerResult


class CodexRunner:
    name = "codex"

    def __init__(
        self,
        *,
        executable: str = "codex",
        model: str | None = "gpt-5.5",
        model_reasoning_effort: str | None = "medium",
        sandbox: str = "workspace-write",
        skip_git_repo_check: bool = False,
    ) -> None:
        self.executable = executable
        self.model = model
        self.model_reasoning_effort = model_reasoning_effort
        self.sandbox = sandbox
        self.skip_git_repo_check = skip_git_repo_check

    def build_command(self, *, cwd: Path, output_last_message: Path) -> list[str]:
        command = [self.executable, "exec", "--sandbox", self.sandbox]
        if self.model:
            command.extend(["-m", self.model])
        if self.model_reasoning_effort:
            command.extend(["-c", f'model_reasoning_effort="{self.model_reasoning_effort}"'])
        command.extend(["--cd", str(cwd), "--output-last-message", str(output_last_message), "--json"])
        if self.skip_git_repo_check:
            command.append("--skip-git-repo-check")
        command.append("-")
        return command

    def run(self, prompt: str, *, cwd: Path, timeout_seconds: int) -> RunnerResult:
        started = time.monotonic()
        log_dir = cwd / "logs" / "codex"
        log_dir.mkdir(parents=True, exist_ok=True)
        stem = f"{int(started * 1_000_000)}"
        last_message_path = log_dir / f"{stem}.last.txt"
        stdout_log_path = log_dir / f"{stem}.stdout.jsonl"
        stderr_log_path = log_dir / f"{stem}.stderr.txt"
        command = self.build_command(cwd=cwd, output_last_message=last_message_path)
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except OSError as exc:
            return RunnerResult(
                runner=self.name,
                command=command,
                exit_code=127,
                stdout="",
                stderr=f"Codex executable not found or could not be executed: {exc}",
                duration_seconds=time.monotonic() - started,
                timed_out=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = _coerce_output(exc.stdout)
            stderr = _coerce_output(exc.stderr) or f"Codex runner timed out after {timeout_seconds} seconds."
            stdout_log_path.write_text(stdout, encoding="utf-8")
            stderr_log_path.write_text(stderr, encoding="utf-8")
            return RunnerResult(
                runner=self.name,
                command=command,
                exit_code=124,
                stdout=stdout,
                stderr=stderr,
                duration_seconds=time.monotonic() - started,
                timed_out=True,
            )

        stdout_log_path.write_text(completed.stdout, encoding="utf-8")
        stderr_log_path.write_text(completed.stderr, encoding="utf-8")
        last_message = _read_text_if_exists(last_message_path)
        return RunnerResult(
            runner=self.name,
            command=command,
            exit_code=completed.returncode,
            stdout=last_message if last_message is not None else completed.stdout,
            stderr=completed.stderr,
            duration_seconds=time.monotonic() - started,
            timed_out=False,
        )


def _read_text_if_exists(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def _coerce_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value
