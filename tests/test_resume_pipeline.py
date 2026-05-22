import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from stock_agents.cli import app
from stock_agents.orchestration.pipeline import resume_shallow_analysis, run_shallow_analysis
from stock_agents.runners.base import RunnerResult
from stock_agents.runners.mock import MockRunner


_ROLE_RE = re.compile(r"^role:\s*(.+)$", re.MULTILINE)


def _role_from_prompt(prompt: str) -> str:
    match = _ROLE_RE.search(prompt)
    assert match is not None
    return match.group(1).strip()


class _FailSecondRoleRunner:
    name = "fail-second-role"

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.mock = MockRunner()

    def run(self, prompt: str, *, cwd: Path, timeout_seconds: int) -> RunnerResult:
        role = _role_from_prompt(prompt)
        self.calls.append(role)
        if len(self.calls) == 2:
            return RunnerResult(
                runner=self.name,
                command=["fail-second-role"],
                exit_code=2,
                stdout="raw output from failed news attempt",
                stderr="simulated runner failure",
                duration_seconds=0.01,
            )
        return self.mock.run(prompt, cwd=cwd, timeout_seconds=timeout_seconds)


class _RecordingMockRunner:
    name = "recording-mock"

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.mock = MockRunner()

    def run(self, prompt: str, *, cwd: Path, timeout_seconds: int) -> RunnerResult:
        self.calls.append(_role_from_prompt(prompt))
        return self.mock.run(prompt, cwd=cwd, timeout_seconds=timeout_seconds)


def _create_run_failed_after_market(tmp_path: Path) -> Path:
    runner = _FailSecondRoleRunner()
    with pytest.raises(RuntimeError):
        run_shallow_analysis(
            ticker="SPY",
            trade_date="2026-01-15",
            runner=runner,
            output_dir=tmp_path,
            run_id="resume-run",
            language="Korean",
            depth="shallow",
        )
    assert runner.calls == ["market_analyst", "news_analyst"]
    return tmp_path / "SPY" / "2026-01-15" / "resume-run"


def test_resume_shallow_analysis_continues_from_first_incomplete_role_without_overwriting_failed_raw(tmp_path):
    run_dir = _create_run_failed_after_market(tmp_path)
    failed_raw_path = run_dir / "outputs/02_news_analyst.attempt0.raw.txt"
    assert failed_raw_path.read_text(encoding="utf-8") == "raw output from failed news attempt\n"

    runner = _RecordingMockRunner()
    result = resume_shallow_analysis(
        run_dir=run_dir,
        runner=runner,
        language="Korean",
        depth="shallow",
        timeout_seconds=60,
    )

    assert runner.calls[0] == "news_analyst"
    assert "market_analyst" not in runner.calls
    assert len(result.completed_roles) == 10
    assert result.final_report_path == run_dir / "reports/final_report.md"
    assert result.final_report_html_path == run_dir / "reports/final_report.html"
    assert result.final_report_path.exists()
    assert result.final_report_html_path.exists()
    assert failed_raw_path.read_text(encoding="utf-8") == "raw output from failed news attempt\n"
    resumed_task_text = (run_dir / "tasks/02_news_analyst.task.md").read_text(encoding="utf-8")
    assert "output_path: outputs/02_news_analyst.attempt1.json" in resumed_task_text
    assert (run_dir / "outputs/02_news_analyst.attempt1.raw.txt").exists()
    assert (run_dir / "outputs/02_news_analyst.attempt1.json").exists()
    state = json.loads((run_dir / "checkpoints/state.json").read_text(encoding="utf-8"))
    assert state["status"] == "completed"
    assert state["current_step"] == "complete"


def test_resume_cli_runs_mock_resume_for_partial_run(tmp_path):
    run_dir = _create_run_failed_after_market(tmp_path)

    result = CliRunner().invoke(app, ["resume", str(run_dir), "--runner", "mock", "--language", "Korean"])

    assert result.exit_code == 0, result.output
    assert str(run_dir) in result.output
    assert str(run_dir / "reports/final_report.md") in result.output
    assert str(run_dir / "reports/final_report.html") in result.output
    state = json.loads((run_dir / "checkpoints/state.json").read_text(encoding="utf-8"))
    assert state["status"] == "completed"
