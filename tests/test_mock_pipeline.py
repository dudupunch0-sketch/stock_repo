import json

from typer.testing import CliRunner

from stock_agents.cli import app
from stock_agents.orchestration.pipeline import run_mock_analysis


def test_run_mock_analysis_writes_full_pipeline_artifacts(tmp_path):
    result = run_mock_analysis(
        ticker="SPY",
        trade_date="2026-01-15",
        output_dir=tmp_path,
        run_id="mock-run",
        language="Korean",
        depth="shallow",
    )

    assert result.run_dir == tmp_path / "SPY" / "2026-01-15" / "mock-run"
    assert (result.run_dir / "tasks/01_market_analyst.task.md").exists()
    assert (result.run_dir / "outputs/01_market_analyst.attempt0.raw.txt").exists()
    assert (result.run_dir / "outputs/01_market_analyst.attempt0.json").exists()
    assert (result.run_dir / "outputs/10_portfolio_manager.latest.json").exists()
    assert (result.run_dir / "reports/final_report.md").exists()
    assert (result.run_dir / "reports/final_report.html").exists()
    assert result.final_report_html_path == result.run_dir / "reports/final_report.html"
    state = json.loads((result.run_dir / "checkpoints/state.json").read_text())
    assert state["status"] == "completed"
    assert state["current_step"] == "complete"
    assert "portfolio_manager" in state["completed_steps"]
    assert state["outputs"]["final_report_html"] == "reports/final_report.html"


def test_analyze_cli_runs_mock_pipeline(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "analyze",
            "SPY",
            "--date",
            "2026-01-15",
            "--runner",
            "mock",
            "--language",
            "Korean",
            "--depth",
            "shallow",
            "--output-dir",
            str(tmp_path),
            "--run-id",
            "cli-run",
        ],
    )

    assert result.exit_code == 0, result.output
    run_dir = tmp_path / "SPY" / "2026-01-15" / "cli-run"
    assert str(run_dir) in result.output
    final_report = (run_dir / "reports/final_report.md").read_text()
    final_report_html = (run_dir / "reports/final_report.html").read_text()
    assert "투자 조언" in final_report
    assert "투자 조언" in final_report_html
