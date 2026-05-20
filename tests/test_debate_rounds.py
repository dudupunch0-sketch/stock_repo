import json

from typer.testing import CliRunner

from stock_agents.cli import app
from stock_agents.domain.enums import Role
from stock_agents.orchestration.pipeline import run_mock_analysis


def test_run_mock_analysis_with_two_debate_rounds_writes_round_artifacts(tmp_path):
    result = run_mock_analysis(
        ticker="SPY",
        trade_date="2026-01-15",
        output_dir=tmp_path,
        run_id="two-rounds",
        language="Korean",
        depth="shallow",
        debate_rounds=2,
    )

    run_dir = tmp_path / "SPY" / "2026-01-15" / "two-rounds"
    assert result.run_dir == run_dir
    assert result.completed_roles.count(Role.BULL_RESEARCHER) == 2
    assert result.completed_roles.count(Role.BEAR_RESEARCHER) == 2

    assert (run_dir / "tasks/03_bull_researcher_round1.task.md").exists()
    assert (run_dir / "tasks/04_bear_researcher_round1.task.md").exists()
    assert (run_dir / "tasks/03_bull_researcher_round2.task.md").exists()
    assert (run_dir / "tasks/04_bear_researcher_round2.task.md").exists()
    assert (run_dir / "outputs/03_bull_researcher_round1.latest.json").exists()
    assert (run_dir / "outputs/04_bear_researcher_round1.latest.json").exists()
    assert (run_dir / "outputs/03_bull_researcher_round2.latest.json").exists()
    assert (run_dir / "outputs/04_bear_researcher_round2.latest.json").exists()

    second_bull_task = (run_dir / "tasks/03_bull_researcher_round2.task.md").read_text(encoding="utf-8")
    assert "outputs/03_bull_researcher_round1.latest.json" in second_bull_task
    assert "outputs/04_bear_researcher_round1.latest.json" in second_bull_task

    manager_task = (run_dir / "tasks/05_research_manager.task.md").read_text(encoding="utf-8")
    assert "outputs/03_bull_researcher_round2.latest.json" in manager_task
    assert "outputs/04_bear_researcher_round2.latest.json" in manager_task

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["debate_rounds"] == 2


def test_analyze_cli_accepts_debate_rounds_for_mock_pipeline(tmp_path):
    result = CliRunner().invoke(
        app,
        [
            "analyze",
            "SPY",
            "--date",
            "2026-01-15",
            "--runner",
            "mock",
            "--debate-rounds",
            "2",
            "--output-dir",
            str(tmp_path),
            "--run-id",
            "cli-two-rounds",
        ],
    )

    assert result.exit_code == 0, result.output
    run_dir = tmp_path / "SPY" / "2026-01-15" / "cli-two-rounds"
    state = json.loads((run_dir / "checkpoints/state.json").read_text(encoding="utf-8"))
    assert "03_bull_researcher_round2" in state["completed_steps"]
    assert "04_bear_researcher_round2" in state["completed_steps"]
