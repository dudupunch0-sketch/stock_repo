from pathlib import Path

from typer.testing import CliRunner

from stock_agents.cli import app
from stock_agents.runners.base import RunnerResult


def test_doctor_cli_accepts_mock_smoke_runner():
    result = CliRunner().invoke(app, ["doctor", "--smoke-runner", "mock"])

    assert result.exit_code == 0, result.output
    assert "mock runner: ok" in result.output
    assert "Hermes" in result.output


def test_run_task_cli_uses_run_root_cwd_for_task_directory(monkeypatch, tmp_path):
    run_dir = tmp_path / "SPY" / "2026-01-15" / "run-1"
    task_dir = run_dir / "tasks"
    task_dir.mkdir(parents=True)
    task_file = task_dir / "01_market_analyst.task.md"
    task_file.write_text("role: market_analyst\nticker: SPY\ntrade_date: 2026-01-15\n", encoding="utf-8")
    calls = {}

    class FakeHermesRunner:
        def __init__(self, *, provider=None, model=None, executable="hermes"):
            pass

        def run(self, prompt: str, *, cwd: Path, timeout_seconds: int) -> RunnerResult:
            calls["cwd"] = cwd
            return RunnerResult(
                runner="hermes",
                command=["hermes", "chat"],
                exit_code=0,
                stdout='{"role": "market_analyst"}',
                stderr="",
                duration_seconds=0.01,
            )

    monkeypatch.setattr("stock_agents.cli.HermesRunner", FakeHermesRunner)
    result = CliRunner().invoke(app, ["run-task", str(task_file), "--runner", "hermes"])

    assert result.exit_code == 0, result.output
    assert calls["cwd"] == run_dir


def test_run_task_cli_resolves_relative_task_inside_tasks_dir(monkeypatch, tmp_path):
    run_dir = tmp_path / "SPY" / "2026-01-15" / "run-1"
    task_dir = run_dir / "tasks"
    task_dir.mkdir(parents=True)
    task_file = task_dir / "01_market_analyst.task.md"
    task_file.write_text("role: market_analyst\nticker: SPY\ntrade_date: 2026-01-15\n", encoding="utf-8")
    calls = {}

    class FakeHermesRunner:
        def __init__(self, *, provider=None, model=None, executable="hermes"):
            pass

        def run(self, prompt: str, *, cwd: Path, timeout_seconds: int) -> RunnerResult:
            calls["cwd"] = cwd
            return RunnerResult(
                runner="hermes",
                command=["hermes", "chat"],
                exit_code=0,
                stdout='{"role": "market_analyst"}',
                stderr="",
                duration_seconds=0.01,
            )

    monkeypatch.setattr("stock_agents.cli.HermesRunner", FakeHermesRunner)
    monkeypatch.chdir(task_dir)
    result = CliRunner().invoke(app, ["run-task", task_file.name, "--runner", "hermes"])

    assert result.exit_code == 0, result.output
    assert calls["cwd"] == run_dir


def test_run_task_cli_supports_fake_hermes_executable_for_smoke(tmp_path):
    task_file = tmp_path / "sample.task.md"
    task_file.write_text("role: market_analyst\nticker: SPY\ntrade_date: 2026-01-15\n", encoding="utf-8")
    fake_hermes = tmp_path / "fake-hermes"
    fake_hermes.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "if '--help' in sys.argv or '--version' in sys.argv:\n"
        "    print('fake hermes')\n"
        "else:\n"
        "    print('{\"role\": \"market_analyst\", \"ticker\": \"SPY\"}')\n",
        encoding="utf-8",
    )
    fake_hermes.chmod(0o755)

    result = CliRunner().invoke(
        app,
        [
            "run-task",
            str(task_file),
            "--runner",
            "hermes",
            "--hermes-executable",
            str(fake_hermes),
            "--timeout-seconds",
            "9",
        ],
    )

    assert result.exit_code == 0, result.output
    assert '"ticker": "SPY"' in result.output


def test_run_task_cli_supports_hermes_runner(monkeypatch, tmp_path):
    task_file = tmp_path / "sample.task.md"
    task_file.write_text("role: market_analyst\nticker: SPY\ntrade_date: 2026-01-15\n", encoding="utf-8")
    calls = {}

    class FakeHermesRunner:
        def __init__(self, *, provider=None, model=None, executable="hermes"):
            calls["provider"] = provider
            calls["model"] = model
            calls["executable"] = executable

        def run(self, prompt: str, *, cwd: Path, timeout_seconds: int) -> RunnerResult:
            calls["prompt"] = prompt
            calls["cwd"] = cwd
            calls["timeout_seconds"] = timeout_seconds
            return RunnerResult(
                runner="hermes",
                command=["hermes", "chat"],
                exit_code=0,
                stdout='{"role": "market_analyst"}',
                stderr="",
                duration_seconds=0.01,
            )

    monkeypatch.setattr("stock_agents.cli.HermesRunner", FakeHermesRunner)
    result = CliRunner().invoke(
        app,
        [
            "run-task",
            str(task_file),
            "--runner",
            "hermes",
            "--provider",
            "openai-codex",
            "--model",
            "gpt-5.5",
            "--timeout-seconds",
            "9",
        ],
    )

    assert result.exit_code == 0, result.output
    assert '{"role": "market_analyst"}' in result.output
    assert calls == {
        "provider": "openai-codex",
        "model": "gpt-5.5",
        "executable": "hermes",
        "prompt": task_file.read_text(encoding="utf-8"),
        "cwd": tmp_path,
        "timeout_seconds": 9,
    }


def test_run_task_cli_supports_codex_runner(monkeypatch, tmp_path):
    task_file = tmp_path / "sample.task.md"
    task_file.write_text("role: market_analyst\nticker: SPY\ntrade_date: 2026-01-15\n", encoding="utf-8")
    calls = {}

    class FakeCodexRunner:
        def __init__(self, *, executable="codex", model="gpt-5.5", model_reasoning_effort="medium"):
            calls["executable"] = executable
            calls["model"] = model
            calls["model_reasoning_effort"] = model_reasoning_effort

        def run(self, prompt: str, *, cwd: Path, timeout_seconds: int) -> RunnerResult:
            calls["prompt"] = prompt
            calls["cwd"] = cwd
            calls["timeout_seconds"] = timeout_seconds
            return RunnerResult(
                runner="codex",
                command=["codex", "exec"],
                exit_code=0,
                stdout='{"role": "market_analyst"}',
                stderr="",
                duration_seconds=0.01,
            )

    monkeypatch.setattr("stock_agents.cli.CodexRunner", FakeCodexRunner)
    result = CliRunner().invoke(
        app,
        [
            "run-task",
            str(task_file),
            "--runner",
            "codex",
            "--codex-executable",
            "fake-codex",
            "--model",
            "gpt-5.5",
            "--reasoning-effort",
            "medium",
            "--timeout-seconds",
            "9",
        ],
    )

    assert result.exit_code == 0, result.output
    assert '{"role": "market_analyst"}' in result.output
    assert calls == {
        "executable": "fake-codex",
        "model": "gpt-5.5",
        "model_reasoning_effort": "medium",
        "prompt": task_file.read_text(encoding="utf-8"),
        "cwd": tmp_path,
        "timeout_seconds": 9,
    }
