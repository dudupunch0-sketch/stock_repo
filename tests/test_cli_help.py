from typer.testing import CliRunner

from stock_agents.cli import app


def test_cli_help_describes_file_handoff_workflow():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    normalized = " ".join(result.output.split())
    assert "TradingAgents" in normalized
    assert "file-handoff" in normalized
    assert "doctor" in normalized
    assert "build-tasks" in normalized


def test_cli_version_option_works_without_subcommand():
    runner = CliRunner()
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_build_tasks_maps_trader_role_to_trader_contract():
    runner = CliRunner()
    result = runner.invoke(app, ["build-tasks", "SPY", "--date", "2026-01-15", "--role", "trader"])

    assert result.exit_code == 0
    assert "role: trader" in result.output
    assert "output_schema: TraderProposalOutput" in result.output
    assert "dependency_output_paths:" in result.output
    assert "05_research_manager.latest.json" in result.output
    assert "AnalystOutput" not in result.output
