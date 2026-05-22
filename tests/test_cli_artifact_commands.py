import json

from typer.testing import CliRunner

from stock_agents.cli import app
from stock_agents.orchestration.pipeline import run_mock_analysis


def test_validate_cli_prints_canonical_json_from_raw_output(tmp_path):
    run = run_mock_analysis(
        ticker="SPY",
        trade_date="2026-01-15",
        output_dir=tmp_path,
        run_id="validate-run",
        language="Korean",
        depth="shallow",
    )
    raw_path = run.run_dir / "outputs/01_market_analyst.attempt0.raw.txt"

    result = CliRunner().invoke(app, ["validate", str(raw_path), "--role", "market_analyst"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["role"] == "market_analyst"
    assert payload["ticker"] == "SPY"
    assert payload["trade_date"] == "2026-01-15"


def test_validate_cli_can_write_canonical_json_to_output_path(tmp_path):
    run = run_mock_analysis(
        ticker="SPY",
        trade_date="2026-01-15",
        output_dir=tmp_path,
        run_id="validate-output-run",
        language="Korean",
        depth="shallow",
    )
    raw_path = run.run_dir / "outputs/10_portfolio_manager.attempt0.raw.txt"
    output_path = tmp_path / "validated.json"

    result = CliRunner().invoke(
        app,
        ["validate", str(raw_path), "--role", "portfolio_manager", "--output", str(output_path)],
    )

    assert result.exit_code == 0, result.output
    assert str(output_path) in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["role"] == "portfolio_manager"
    assert payload["not_financial_advice"] is True


def test_show_run_cli_summarizes_checkpoint_outputs_and_report(tmp_path):
    run = run_mock_analysis(
        ticker="SPY",
        trade_date="2026-01-15",
        output_dir=tmp_path,
        run_id="show-run",
        language="Korean",
        depth="shallow",
    )

    result = CliRunner().invoke(app, ["show-run", str(run.run_dir)])

    assert result.exit_code == 0, result.output
    assert "Run: show-run" in result.output
    assert "Status: completed" in result.output
    assert "Current step: complete" in result.output
    assert "portfolio_manager: outputs/10_portfolio_manager.latest.json" in result.output
    assert f"Final report: {run.run_dir / 'reports/final_report.md'}" in result.output
    assert f"Final report HTML: {run.run_dir / 'reports/final_report.html'}" in result.output
