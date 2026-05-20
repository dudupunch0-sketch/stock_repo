import json

from typer.testing import CliRunner

from stock_agents.cli import app
from stock_agents.domain.enums import Role
from stock_agents.orchestration.pipeline import run_mock_analysis


def test_run_mock_analysis_with_two_risk_rounds_writes_round_artifacts(tmp_path):
    result = run_mock_analysis(
        ticker="SPY",
        trade_date="2026-01-15",
        output_dir=tmp_path,
        run_id="two-risk-rounds",
        language="Korean",
        depth="shallow",
        risk_rounds=2,
    )

    run_dir = tmp_path / "SPY" / "2026-01-15" / "two-risk-rounds"
    assert result.run_dir == run_dir
    assert result.completed_roles.count(Role.RISK_AGGRESSIVE) == 2
    assert result.completed_roles.count(Role.RISK_CONSERVATIVE) == 2
    assert result.completed_roles.count(Role.RISK_NEUTRAL) == 2

    for round_number in (1, 2):
        assert (run_dir / f"tasks/07_risk_aggressive_round{round_number}.task.md").exists()
        assert (run_dir / f"tasks/08_risk_conservative_round{round_number}.task.md").exists()
        assert (run_dir / f"tasks/09_risk_neutral_round{round_number}.task.md").exists()
        assert (run_dir / f"outputs/07_risk_aggressive_round{round_number}.latest.json").exists()
        assert (run_dir / f"outputs/08_risk_conservative_round{round_number}.latest.json").exists()
        assert (run_dir / f"outputs/09_risk_neutral_round{round_number}.latest.json").exists()

    second_aggressive_task = (run_dir / "tasks/07_risk_aggressive_round2.task.md").read_text(encoding="utf-8")
    assert "outputs/07_risk_aggressive_round1.latest.json" in second_aggressive_task
    assert "outputs/08_risk_conservative_round1.latest.json" in second_aggressive_task
    assert "outputs/09_risk_neutral_round1.latest.json" in second_aggressive_task

    portfolio_task = (run_dir / "tasks/10_portfolio_manager.task.md").read_text(encoding="utf-8")
    assert "outputs/07_risk_aggressive_round2.latest.json" in portfolio_task
    assert "outputs/08_risk_conservative_round2.latest.json" in portfolio_task
    assert "outputs/09_risk_neutral_round2.latest.json" in portfolio_task

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["risk_rounds"] == 2


def test_analyze_cli_accepts_risk_rounds_for_mock_pipeline(tmp_path):
    result = CliRunner().invoke(
        app,
        [
            "analyze",
            "SPY",
            "--date",
            "2026-01-15",
            "--runner",
            "mock",
            "--risk-rounds",
            "2",
            "--output-dir",
            str(tmp_path),
            "--run-id",
            "cli-risk-rounds",
        ],
    )

    assert result.exit_code == 0, result.output
    run_dir = tmp_path / "SPY" / "2026-01-15" / "cli-risk-rounds"
    state = json.loads((run_dir / "checkpoints/state.json").read_text(encoding="utf-8"))
    assert "07_risk_aggressive_round2" in state["completed_steps"]
    assert "08_risk_conservative_round2" in state["completed_steps"]
    assert "09_risk_neutral_round2" in state["completed_steps"]


def test_resume_cli_reuses_manifest_risk_rounds(tmp_path):
    run_mock_analysis(
        ticker="SPY",
        trade_date="2026-01-15",
        output_dir=tmp_path,
        run_id="resume-risk-rounds",
        language="Korean",
        depth="shallow",
        risk_rounds=2,
    )
    run_dir = tmp_path / "SPY" / "2026-01-15" / "resume-risk-rounds"

    state_path = run_dir / "checkpoints/state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    incomplete_steps = {
        "07_risk_aggressive_round2",
        "08_risk_conservative_round2",
        "09_risk_neutral_round2",
        "portfolio_manager",
        "render_final_report",
    }
    state["completed_steps"] = [step for step in state["completed_steps"] if step not in incomplete_steps]
    for output_key in [
        "07_risk_aggressive_round2",
        "08_risk_conservative_round2",
        "09_risk_neutral_round2",
        "risk_aggressive",
        "risk_conservative",
        "risk_neutral",
        "portfolio_manager",
        "final_report",
    ]:
        state["outputs"].pop(output_key, None)
    state["status"] = "running"
    state["current_step"] = "07_risk_aggressive_round2"
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    result = CliRunner().invoke(app, ["resume", str(run_dir), "--runner", "mock", "--language", "Korean"])

    assert result.exit_code == 0, result.output
    resumed_state = json.loads(state_path.read_text(encoding="utf-8"))
    assert "07_risk_aggressive_round2" in resumed_state["completed_steps"]
    assert "08_risk_conservative_round2" in resumed_state["completed_steps"]
    assert "09_risk_neutral_round2" in resumed_state["completed_steps"]
    assert (run_dir / "outputs/07_risk_aggressive_round2.attempt1.json").exists()
    assert (run_dir / "outputs/08_risk_conservative_round2.attempt1.json").exists()
    assert (run_dir / "outputs/09_risk_neutral_round2.attempt1.json").exists()
