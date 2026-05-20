from pathlib import Path
from subprocess import CompletedProcess

from stock_agents.domain.enums import Role
from stock_agents.orchestration.task_builder import build_agent_task, render_task
from stock_agents.runners.codex import CodexRunner


def test_codex_runner_builds_workspace_write_exec_command(tmp_path):
    runner = CodexRunner(
        executable="codex",
        model="gpt-5.5",
        model_reasoning_effort="medium",
        sandbox="workspace-write",
    )
    last_message_path = tmp_path / "logs" / "codex" / "last.txt"

    command = runner.build_command(
        cwd=tmp_path,
        output_last_message=last_message_path,
    )

    assert command == [
        "codex",
        "exec",
        "--sandbox",
        "workspace-write",
        "-m",
        "gpt-5.5",
        "-c",
        'model_reasoning_effort="medium"',
        "--cd",
        str(tmp_path),
        "--output-last-message",
        str(last_message_path),
        "--json",
        "-",
    ]


def test_codex_runner_builds_skip_git_repo_check_command(tmp_path):
    runner = CodexRunner(executable="codex", sandbox="read-only", skip_git_repo_check=True)

    command = runner.build_command(
        cwd=tmp_path,
        output_last_message=tmp_path / "last.txt",
    )

    assert command[0:4] == ["codex", "exec", "--sandbox", "read-only"]
    assert "--skip-git-repo-check" in command
    assert command[-1] == "-"


def test_codex_runner_run_uses_last_message_as_stdout_and_stores_logs(monkeypatch, tmp_path):
    calls = {}

    def fake_run(command, *, cwd, input, capture_output, text, timeout, check):
        calls["command"] = command
        calls["cwd"] = cwd
        calls["input"] = input
        calls["capture_output"] = capture_output
        calls["text"] = text
        calls["timeout"] = timeout
        calls["check"] = check
        last_message_path = Path(command[command.index("--output-last-message") + 1])
        last_message_path.parent.mkdir(parents=True, exist_ok=True)
        last_message_path.write_text('{"ok": true}', encoding="utf-8")
        return CompletedProcess(command, 0, stdout='{"event":"done"}\n', stderr="codex stderr")

    monkeypatch.setattr("stock_agents.runners.codex.subprocess.run", fake_run)
    result = CodexRunner(executable="codex").run("prompt", cwd=tmp_path, timeout_seconds=7)

    assert calls["command"][0:4] == ["codex", "exec", "--sandbox", "workspace-write"]
    assert calls["command"][-1] == "-"
    assert "--json" in calls["command"]
    assert calls["cwd"] == tmp_path
    assert calls["input"] == "prompt"
    assert calls["capture_output"] is True
    assert calls["text"] is True
    assert calls["timeout"] == 7
    assert calls["check"] is False
    assert result.exit_code == 0
    assert result.stdout == '{"ok": true}'
    assert result.stderr == "codex stderr"
    assert list((tmp_path / "logs" / "codex").glob("*.stdout.jsonl"))
    assert list((tmp_path / "logs" / "codex").glob("*.stderr.txt"))
    assert list((tmp_path / "logs" / "codex").glob("*.last.txt"))


def test_codex_runner_passes_frontmatter_task_prompt_on_stdin(monkeypatch, tmp_path):
    task = build_agent_task(role=Role.MARKET_ANALYST, ticker="SPY", trade_date="2026-01-15", language="Korean")
    prompt = render_task(task)
    assert prompt.startswith("---")
    calls = {}

    def fake_run(command, *, cwd, input, capture_output, text, timeout, check):
        calls["command"] = command
        calls["input"] = input
        last_message_path = Path(command[command.index("--output-last-message") + 1])
        last_message_path.parent.mkdir(parents=True, exist_ok=True)
        last_message_path.write_text('{"ok": true}', encoding="utf-8")
        return CompletedProcess(command, 0, stdout='{"event":"done"}\n', stderr="")

    monkeypatch.setattr("stock_agents.runners.codex.subprocess.run", fake_run)

    result = CodexRunner(executable="codex").run(prompt, cwd=tmp_path, timeout_seconds=7)

    assert result.exit_code == 0
    assert calls["command"][-1] == "-"
    assert prompt not in calls["command"]
    assert calls["input"] == prompt


def test_codex_runner_reports_missing_executable(tmp_path):
    result = CodexRunner(executable="definitely-not-real-codex-binary").run(
        "prompt",
        cwd=tmp_path,
        timeout_seconds=1,
    )

    assert result.exit_code == 127
    assert result.timed_out is False
    assert "not found" in result.stderr
    assert result.command[:2] == ["definitely-not-real-codex-binary", "exec"]
