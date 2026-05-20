from pathlib import Path

from stock_agents.doctor import CheckStatus, check_codex_installation, check_hermes_installation, run_doctor
from stock_agents.runners.base import RunnerResult


def test_check_hermes_installation_reports_missing_binary():
    status = check_hermes_installation(executable="definitely-not-a-real-hermes-binary")

    assert status.name == "hermes"
    assert status.ok is False
    assert "not found" in status.message


def test_check_codex_installation_reports_missing_binary():
    status = check_codex_installation(executable="definitely-not-a-real-codex-binary")

    assert status.name == "codex"
    assert status.ok is False
    assert "not found" in status.message


def test_run_doctor_includes_mock_runner_without_external_llm():
    report = run_doctor(smoke_runner="mock")

    assert "mock runner: ok" in report
    assert "Hermes" in report
    assert "Codex" in report


def test_run_doctor_codex_smoke_requires_successful_exec(monkeypatch):
    calls = {}

    class FakeCodexRunner:
        def __init__(
            self,
            *,
            executable="codex",
            model="gpt-5.5",
            model_reasoning_effort="medium",
            sandbox="workspace-write",
            skip_git_repo_check=False,
        ):
            assert executable == "fake-codex"
            assert model == "gpt-5.5"
            assert model_reasoning_effort == "medium"
            assert sandbox == "read-only"
            assert skip_git_repo_check is True

        def run(self, prompt, *, cwd, timeout_seconds):
            calls["cwd"] = cwd
            assert "{\"ok\": true}" in prompt
            return RunnerResult(
                runner="codex",
                command=["fake-codex", "exec"],
                exit_code=0,
                stdout='{"ok": true}',
                stderr="",
                duration_seconds=0.01,
            )

    monkeypatch.setattr("stock_agents.doctor.check_codex_installation", lambda executable: CheckStatus(name="codex", ok=True, message="found fake codex"))
    monkeypatch.setattr("stock_agents.doctor.CodexRunner", FakeCodexRunner)

    report = run_doctor(smoke_runner="codex", codex_executable="fake-codex")

    assert "Codex: found fake codex" in report
    assert "codex runner: ok" in report
    assert calls["cwd"] != Path.cwd()
    assert calls["cwd"].name.startswith("stock-agents-codex-smoke-")


def test_run_doctor_codex_smoke_marks_failed_exec_unavailable(monkeypatch):
    class FailingCodexRunner:
        def __init__(
            self,
            *,
            executable="codex",
            model="gpt-5.5",
            model_reasoning_effort="medium",
            sandbox="workspace-write",
            skip_git_repo_check=False,
        ):
            assert sandbox == "read-only"
            assert skip_git_repo_check is True

        def run(self, prompt, *, cwd, timeout_seconds):
            return RunnerResult(
                runner="codex",
                command=["fake-codex", "exec"],
                exit_code=1,
                stdout="",
                stderr="refresh token failure",
                duration_seconds=0.01,
            )

    monkeypatch.setattr("stock_agents.doctor.check_codex_installation", lambda executable: CheckStatus(name="codex", ok=True, message="found fake codex"))
    monkeypatch.setattr("stock_agents.doctor.CodexRunner", FailingCodexRunner)

    report = run_doctor(smoke_runner="codex", codex_executable="fake-codex")

    assert "codex runner: unavailable" in report
    assert "refresh token failure" in report
