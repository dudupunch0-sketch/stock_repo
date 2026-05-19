from pathlib import Path

from typer.testing import CliRunner

from stock_agents.cli import app
from stock_agents.domain.enums import Role
from stock_agents.orchestration.repair import build_repair_task
from stock_agents.orchestration.pipeline import run_shallow_analysis
from stock_agents.orchestration.task_builder import build_agent_task, render_task
from stock_agents.runners.base import RunnerResult
from stock_agents.runners.mock import MockRunner


def test_repair_prompt_contains_original_task_raw_error_and_schema():
    task = build_agent_task(role=Role.MARKET_ANALYST, ticker="SPY", trade_date="2026-01-15", language="Korean")
    task_text = render_task(task)

    repair_text = build_repair_task(
        task=task,
        original_task_text=task_text,
        raw_output="not json",
        validation_error="could not find JSON object in runner output",
        attempt_number=1,
    )

    assert "# Repair attempt 1 for 01_market_analyst" in repair_text
    assert "role: market_analyst" in repair_text
    assert "ticker: SPY" in repair_text
    assert "AnalystOutput" in repair_text
    assert "not json" in repair_text
    assert "could not find JSON object" in repair_text
    assert "Do not add new facts" in repair_text
    assert "Return exactly one corrected JSON object" in repair_text


def test_run_shallow_analysis_repairs_invalid_first_attempt(tmp_path):
    class OneRepairRunner:
        name = "one-repair"

        def __init__(self) -> None:
            self.calls = 0
            self.mock = MockRunner()

        def run(self, prompt: str, *, cwd: Path, timeout_seconds: int) -> RunnerResult:
            self.calls += 1
            if self.calls == 1:
                return RunnerResult(
                    runner=self.name,
                    command=["fake-runner"],
                    exit_code=0,
                    stdout="not json",
                    stderr="",
                    duration_seconds=0.01,
                )
            return self.mock.run(prompt, cwd=cwd, timeout_seconds=timeout_seconds)

    runner = OneRepairRunner()

    result = run_shallow_analysis(
        ticker="SPY",
        trade_date="2026-01-15",
        runner=runner,
        output_dir=tmp_path,
        run_id="repair-run",
        language="Korean",
        depth="shallow",
    )

    run_dir = result.run_dir
    assert runner.calls == 11
    assert (run_dir / "outputs/01_market_analyst.attempt0.raw.txt").read_text(encoding="utf-8") == "not json\n"
    assert (run_dir / "repairs/01_market_analyst.attempt1.repair.task.md").exists()
    assert (run_dir / "outputs/01_market_analyst.attempt1.raw.txt").exists()
    assert (run_dir / "outputs/01_market_analyst.attempt1.json").exists()
    assert (run_dir / "outputs/01_market_analyst.latest.json").read_text(encoding="utf-8") == (
        run_dir / "outputs/01_market_analyst.attempt1.json"
    ).read_text(encoding="utf-8")
    assert len(result.completed_roles) == 10


def test_analyze_cli_runs_hermes_pipeline_with_repair_options(monkeypatch, tmp_path):
    calls = {"init": None, "timeouts": []}

    class FakeHermesRunner:
        name = "hermes"

        def __init__(self, *, provider=None, model=None, executable="hermes"):
            calls["init"] = {"provider": provider, "model": model, "executable": executable}
            self.mock = MockRunner()

        def run(self, prompt: str, *, cwd: Path, timeout_seconds: int) -> RunnerResult:
            calls["timeouts"].append(timeout_seconds)
            return self.mock.run(prompt, cwd=cwd, timeout_seconds=timeout_seconds)

    monkeypatch.setattr("stock_agents.cli.HermesRunner", FakeHermesRunner)

    result = CliRunner().invoke(
        app,
        [
            "analyze",
            "SPY",
            "--date",
            "2026-01-15",
            "--runner",
            "hermes",
            "--provider",
            "openai-codex",
            "--model",
            "gpt-5.5",
            "--hermes-executable",
            "fake-hermes",
            "--timeout-seconds",
            "9",
            "--language",
            "Korean",
            "--depth",
            "shallow",
            "--output-dir",
            str(tmp_path),
            "--run-id",
            "cli-hermes-run",
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls["init"] == {"provider": "openai-codex", "model": "gpt-5.5", "executable": "fake-hermes"}
    assert calls["timeouts"] == [9] * 10
    assert str(tmp_path / "SPY" / "2026-01-15" / "cli-hermes-run") in result.output
