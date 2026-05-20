import json

from typer.testing import CliRunner

from stock_agents.cli import app
from stock_agents.domain.enums import Role
from stock_agents.orchestration.pipeline import resolve_analyst_roles, run_mock_analysis


def test_resolve_analysts_all_expands_all_supported_analyst_roles():
    assert resolve_analyst_roles("all") == (
        Role.MARKET_ANALYST,
        Role.SENTIMENT_ANALYST,
        Role.NEWS_ANALYST,
        Role.FUNDAMENTALS_ANALYST,
    )


def test_run_mock_analysis_with_all_analysts_writes_all_analyst_artifacts_and_dependencies(tmp_path):
    result = run_mock_analysis(
        ticker="SPY",
        trade_date="2026-01-15",
        output_dir=tmp_path,
        run_id="all-analysts-run",
        language="Korean",
        depth="shallow",
        analysts="all",
    )

    run_dir = tmp_path / "SPY" / "2026-01-15" / "all-analysts-run"
    assert result.run_dir == run_dir
    assert result.completed_roles[:4] == [
        Role.MARKET_ANALYST,
        Role.SENTIMENT_ANALYST,
        Role.NEWS_ANALYST,
        Role.FUNDAMENTALS_ANALYST,
    ]
    assert (run_dir / "tasks/02_sentiment_analyst.task.md").exists()
    assert (run_dir / "tasks/02_fundamentals_analyst.task.md").exists()
    assert (run_dir / "outputs/02_sentiment_analyst.latest.json").exists()
    assert (run_dir / "outputs/02_fundamentals_analyst.latest.json").exists()

    bull_task = (run_dir / "tasks/03_bull_researcher.task.md").read_text(encoding="utf-8")
    assert "outputs/01_market_analyst.latest.json" in bull_task
    assert "outputs/02_sentiment_analyst.latest.json" in bull_task
    assert "outputs/02_news_analyst.latest.json" in bull_task
    assert "outputs/02_fundamentals_analyst.latest.json" in bull_task

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["analyst_roles"] == [
        "market_analyst",
        "sentiment_analyst",
        "news_analyst",
        "fundamentals_analyst",
    ]


def test_analyze_cli_accepts_analysts_all_for_mock_pipeline(tmp_path):
    result = CliRunner().invoke(
        app,
        [
            "analyze",
            "SPY",
            "--date",
            "2026-01-15",
            "--runner",
            "mock",
            "--analysts",
            "all",
            "--language",
            "Korean",
            "--depth",
            "shallow",
            "--output-dir",
            str(tmp_path),
            "--run-id",
            "cli-all-analysts-run",
        ],
    )

    assert result.exit_code == 0, result.output
    run_dir = tmp_path / "SPY" / "2026-01-15" / "cli-all-analysts-run"
    state = json.loads((run_dir / "checkpoints/state.json").read_text(encoding="utf-8"))
    assert "sentiment_analyst" in state["completed_steps"]
    assert "fundamentals_analyst" in state["completed_steps"]


def test_analyze_cli_rejects_unknown_analyst(tmp_path):
    result = CliRunner().invoke(
        app,
        [
            "analyze",
            "SPY",
            "--date",
            "2026-01-15",
            "--runner",
            "mock",
            "--analysts",
            "macro",
            "--output-dir",
            str(tmp_path),
            "--run-id",
            "bad-analyst-run",
        ],
    )

    assert result.exit_code != 0
    assert "unknown analyst" in result.output
