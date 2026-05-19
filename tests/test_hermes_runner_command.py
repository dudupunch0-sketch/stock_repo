from pathlib import Path
from subprocess import CompletedProcess

from stock_agents.runners.hermes import HermesRunner


def test_hermes_runner_builds_quiet_programmatic_command():
    runner = HermesRunner(executable="hermes", provider="openai-codex", model="gpt-5.5")

    command = runner.build_command("Return JSON")

    assert command == [
        "hermes",
        "chat",
        "-Q",
        "--provider",
        "openai-codex",
        "-m",
        "gpt-5.5",
        "-q",
        "Return JSON",
        "--source",
        "stock-agents",
    ]


def test_hermes_runner_run_uses_subprocess_without_shell(monkeypatch, tmp_path):
    calls = {}

    def fake_run(command, *, cwd, capture_output, text, timeout, check):
        calls["command"] = command
        calls["cwd"] = cwd
        calls["capture_output"] = capture_output
        calls["text"] = text
        calls["timeout"] = timeout
        calls["check"] = check
        return CompletedProcess(command, 0, stdout='{"ok": true}', stderr="")

    monkeypatch.setattr("stock_agents.runners.hermes.subprocess.run", fake_run)
    result = HermesRunner(executable="hermes").run("prompt", cwd=tmp_path, timeout_seconds=7)

    assert calls["command"][0:3] == ["hermes", "chat", "-Q"]
    assert calls["cwd"] == tmp_path
    assert calls["capture_output"] is True
    assert calls["text"] is True
    assert calls["timeout"] == 7
    assert calls["check"] is False
    assert result.exit_code == 0
    assert result.stdout == '{"ok": true}'


def test_hermes_runner_reports_missing_executable(tmp_path):
    result = HermesRunner(executable="definitely-not-real-hermes-binary").run(
        "prompt",
        cwd=tmp_path,
        timeout_seconds=1,
    )

    assert result.exit_code == 127
    assert result.timed_out is False
    assert "not found" in result.stderr
    assert result.command[:3] == ["definitely-not-real-hermes-binary", "chat", "-Q"]
