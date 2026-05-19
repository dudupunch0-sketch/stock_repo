from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from pydantic import BaseModel

from stock_agents.orchestration.validator import extract_json_object, validate_output_for_role
from stock_agents.runners.hermes import HermesRunner
from stock_agents.runners.mock import MockRunner
from stock_agents.domain.enums import Role


class CheckStatus(BaseModel):
    name: str
    ok: bool
    message: str


def check_hermes_installation(*, executable: str = "hermes") -> CheckStatus:
    path = shutil.which(executable)
    if path is None:
        return CheckStatus(name="hermes", ok=False, message=f"{executable} not found on PATH")

    try:
        completed = subprocess.run(
            [path, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except OSError as exc:
        return CheckStatus(name="hermes", ok=False, message=f"{path} could not be executed: {exc}")
    except subprocess.TimeoutExpired:
        return CheckStatus(name="hermes", ok=False, message=f"{path} --version timed out")

    version_text = (completed.stdout or completed.stderr).strip()
    if completed.returncode != 0:
        detail = f": {version_text}" if version_text else ""
        return CheckStatus(name="hermes", ok=False, message=f"{path} --version failed{detail}")
    suffix = f" ({version_text})" if version_text else ""
    return CheckStatus(name="hermes", ok=True, message=f"found at {path}{suffix}")


def run_doctor(*, smoke_runner: str | None = "mock", hermes_executable: str = "hermes") -> str:
    normalized_runner = (smoke_runner or "none").lower()
    if normalized_runner not in {"none", "mock", "hermes"}:
        raise ValueError("smoke_runner must be one of: none, mock, hermes")

    hermes_status = check_hermes_installation(executable=hermes_executable)
    lines = [
        "Stock Agents Doctor",
        f"Hermes: {hermes_status.message}",
    ]

    if normalized_runner == "mock":
        lines.append(_mock_smoke_line())
    elif normalized_runner == "hermes":
        lines.append(_hermes_smoke_line(executable=hermes_executable, installed=hermes_status.ok))
    else:
        lines.append("runner smoke: skipped")
    return "\n".join(lines)


def _mock_smoke_line() -> str:
    prompt = "role: market_analyst\nticker: SPY\ntrade_date: 2026-01-15\n"
    result = MockRunner().run(prompt, cwd=Path.cwd(), timeout_seconds=5)
    payload = extract_json_object(result.stdout)
    validate_output_for_role(Role.MARKET_ANALYST, payload)
    return "mock runner: ok"


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
