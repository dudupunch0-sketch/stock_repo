from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from pydantic import BaseModel

from stock_agents.domain.enums import Role
from stock_agents.orchestration.validator import extract_json_object, validate_output_for_role
from stock_agents.runners.codex import CodexRunner
from stock_agents.runners.hermes import HermesRunner
from stock_agents.runners.mock import MockRunner


class CheckStatus(BaseModel):
    name: str
    ok: bool
    message: str


def check_hermes_installation(*, executable: str = "hermes") -> CheckStatus:
    return _check_cli_installation(name="hermes", executable=executable)


def check_codex_installation(*, executable: str = "codex") -> CheckStatus:
    return _check_cli_installation(name="codex", executable=executable)


def _check_cli_installation(*, name: str, executable: str) -> CheckStatus:
    path = shutil.which(executable)
    if path is None:
        return CheckStatus(name=name, ok=False, message=f"{executable} not found on PATH")

    try:
        completed = subprocess.run(
            [path, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except OSError as exc:
        return CheckStatus(name=name, ok=False, message=f"{path} could not be executed: {exc}")
    except subprocess.TimeoutExpired:
        return CheckStatus(name=name, ok=False, message=f"{path} --version timed out")

    version_text = (completed.stdout or completed.stderr).strip()
    if completed.returncode != 0:
        detail = f": {version_text}" if version_text else ""
        return CheckStatus(name=name, ok=False, message=f"{path} --version failed{detail}")
    suffix = f" ({version_text})" if version_text else ""
    return CheckStatus(name=name, ok=True, message=f"found at {path}{suffix}")


def run_doctor(
    *,
    smoke_runner: str | None = "mock",
    hermes_executable: str = "hermes",
    codex_executable: str = "codex",
) -> str:
    normalized_runner = (smoke_runner or "none").lower()
    if normalized_runner not in {"none", "mock", "hermes", "codex"}:
        raise ValueError("smoke_runner must be one of: none, mock, hermes, codex")

    hermes_status = check_hermes_installation(executable=hermes_executable)
    codex_status = check_codex_installation(executable=codex_executable)
    lines = [
        "Stock Agents Doctor",
        f"Hermes: {hermes_status.message}",
        f"Codex: {codex_status.message}",
    ]

    if normalized_runner == "mock":
        lines.append(_mock_smoke_line())
    elif normalized_runner == "hermes":
        lines.append(_hermes_smoke_line(executable=hermes_executable, installed=hermes_status.ok))
    elif normalized_runner == "codex":
        lines.append(_codex_smoke_line(executable=codex_executable, installed=codex_status.ok))
    else:
        lines.append("runner smoke: skipped")
    return "\n".join(lines)


def _mock_smoke_line() -> str:
    prompt = "role: market_analyst\nticker: SPY\ntrade_date: 2026-01-15\n"
    result = MockRunner().run(prompt, cwd=Path.cwd(), timeout_seconds=5)
    payload = extract_json_object(result.stdout)
    validate_output_for_role(Role.MARKET_ANALYST, payload)
    return "mock runner: ok"


def _codex_smoke_line(*, executable: str, installed: bool) -> str:
    if not installed:
        return "codex runner: unavailable"
    with tempfile.TemporaryDirectory(prefix="stock-agents-codex-smoke-") as smoke_dir:
        result = CodexRunner(executable=executable, sandbox="read-only", skip_git_repo_check=True).run(
            "Return only this JSON object and no other text: {\"ok\": true}",
            cwd=Path(smoke_dir),
            timeout_seconds=60,
        )
    if result.exit_code != 0:
        detail = (result.stderr or result.stdout).strip()
        suffix = f" ({detail})" if detail else ""
        return f"codex runner: unavailable{suffix}"
    try:
        payload = extract_json_object(result.stdout)
    except ValueError as exc:
        return f"codex runner: unavailable ({exc})"
    if payload.get("ok") is not True:
        return "codex runner: unavailable (smoke output did not contain ok=true)"
    return "codex runner: ok"


def _hermes_smoke_line(*, executable: str, installed: bool) -> str:
    if not installed:
        return "hermes runner: unavailable"
    command = HermesRunner(executable=executable).build_command("Return only this JSON object: {\"ok\": true}")
    # Do not call the LLM from doctor. The smoke check only proves that the
    # configured Hermes executable supports the programmatic chat command shape.
    help_command = command[:3] + ["--help"]
    try:
        completed = subprocess.run(
            help_command,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"hermes runner: unavailable ({exc})"
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        return f"hermes runner: unavailable ({detail})"
    return "hermes runner: ok"
