import pytest
from typer.testing import CliRunner

from stock_agents.cli import app
from stock_agents.orchestration.pipeline import resolve_debate_rounds, resolve_risk_rounds, run_mock_analysis


def _assert_valid_range_message(output: str) -> None:
    assert "between 1 and 3" in output or "1<=x<=3" in output


def test_debate_rounds_are_limited_to_one_through_three():
    assert resolve_debate_rounds(1) == 1
    assert resolve_debate_rounds(3) == 3

    with pytest.raises(ValueError, match="between 1 and 3"):
        resolve_debate_rounds(0)
    with pytest.raises(ValueError, match="between 1 and 3"):
        resolve_debate_rounds(4)


def test_risk_rounds_are_limited_to_one_through_three():
    assert resolve_risk_rounds(1) == 1
    assert resolve_risk_rounds(3) == 3

    with pytest.raises(ValueError, match="between 1 and 3"):
        resolve_risk_rounds(0)
    with pytest.raises(ValueError, match="between 1 and 3"):
        resolve_risk_rounds(4)


def test_mock_pipeline_accepts_max_rounds(tmp_path):
    result = run_mock_analysis(
        ticker="SPY",
        trade_date="2026-01-15",
        output_dir=tmp_path,
        run_id="max-rounds",
        language="Korean",
        depth="shallow",
        debate_rounds=3,
        risk_rounds=3,
    )

    run_dir = tmp_path / "SPY" / "2026-01-15" / "max-rounds"
    assert result.run_dir == run_dir
    assert (run_dir / "outputs/03_bull_researcher_round3.latest.json").exists()
    assert (run_dir / "outputs/04_bear_researcher_round3.latest.json").exists()
    assert (run_dir / "outputs/07_risk_aggressive_round3.latest.json").exists()
    assert (run_dir / "outputs/08_risk_conservative_round3.latest.json").exists()
    assert (run_dir / "outputs/09_risk_neutral_round3.latest.json").exists()


def test_analyze_cli_rejects_debate_rounds_above_max(tmp_path):
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
            "4",
            "--output-dir",
            str(tmp_path),
            "--run-id",
            "too-many-debate-rounds",
        ],
    )

    assert result.exit_code != 0
    _assert_valid_range_message(result.output)
    assert not (tmp_path / "SPY" / "2026-01-15" / "too-many-debate-rounds").exists()


def test_analyze_cli_rejects_risk_rounds_above_max(tmp_path):
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
            "4",
            "--output-dir",
            str(tmp_path),
            "--run-id",
            "too-many-risk-rounds",
        ],
    )

    assert result.exit_code != 0
    _assert_valid_range_message(result.output)
    assert not (tmp_path / "SPY" / "2026-01-15" / "too-many-risk-rounds").exists()


def test_round_limit_is_documented_in_cli_help():
    for command in ("analyze", "resume"):
        result = CliRunner().invoke(app, [command, "--help"])

        assert result.exit_code == 0, result.output
        normalized_help = " ".join(result.output.split())
        assert "--debate-rounds" in result.output
        assert "--risk-rounds" in result.output
        assert "Valid range: 1..3" in normalized_help
