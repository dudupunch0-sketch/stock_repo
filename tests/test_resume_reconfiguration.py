import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from stock_agents.cli import app
from stock_agents.orchestration.pipeline import resume_shallow_analysis, run_mock_analysis
from stock_agents.runners.mock import MockRunner


class _NoRunRunner:
    name = "no-run"

    def run(self, prompt: str, *, cwd: Path, timeout_seconds: int):  # pragma: no cover - should never be reached.
        raise AssertionError("resume mismatch validation should run before scheduling tasks")


def _run_dir(tmp_path: Path, run_id: str) -> Path:
    return tmp_path / "SPY" / "2026-01-15" / run_id


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _artifact_names(run_dir: Path) -> set[str]:
    return {str(path.relative_to(run_dir)) for path in run_dir.rglob("*") if path.is_file()}


def _mark_steps_incomplete(run_dir: Path, *, completed_steps: set[str], output_keys: set[str]) -> None:
    state_path = run_dir / "checkpoints/state.json"
    state = _load_json(state_path)
    state["completed_steps"] = [step for step in state["completed_steps"] if step not in completed_steps]
    for key in output_keys:
        state["outputs"].pop(key, None)
    state["status"] = "running"
    state["current_step"] = next(iter(completed_steps))
    _write_json(state_path, state)


def _assert_resume_mismatch(exc: pytest.ExceptionInfo[ValueError], option_name: str, manifest_value: str, requested_value: str) -> None:
    message = str(exc.value)
    assert option_name in message
    assert f"manifest has {manifest_value}" in message
    assert f"requested {requested_value}" in message
    assert "Start a new run" in message


def test_resume_rejects_mismatched_risk_rounds_before_running(tmp_path):
    run_mock_analysis(
        ticker="SPY",
        trade_date="2026-01-15",
        output_dir=tmp_path,
        run_id="risk-mismatch",
        language="Korean",
        depth="shallow",
        risk_rounds=2,
    )
    run_dir = _run_dir(tmp_path, "risk-mismatch")
    _mark_steps_incomplete(
        run_dir,
        completed_steps={"07_risk_aggressive_round2", "08_risk_conservative_round2", "09_risk_neutral_round2"},
        output_keys={"07_risk_aggressive_round2", "08_risk_conservative_round2", "09_risk_neutral_round2"},
    )
    before_artifacts = _artifact_names(run_dir)

    with pytest.raises(ValueError) as exc:
        resume_shallow_analysis(run_dir=run_dir, runner=_NoRunRunner(), risk_rounds=1)

    _assert_resume_mismatch(exc, "--risk-rounds", "2", "1")
    assert _artifact_names(run_dir) == before_artifacts


def test_resume_rejects_mismatched_debate_rounds_before_running(tmp_path):
    run_mock_analysis(
        ticker="SPY",
        trade_date="2026-01-15",
        output_dir=tmp_path,
        run_id="debate-mismatch",
        language="Korean",
        depth="shallow",
        debate_rounds=2,
    )
    run_dir = _run_dir(tmp_path, "debate-mismatch")
    before_artifacts = _artifact_names(run_dir)

    with pytest.raises(ValueError) as exc:
        resume_shallow_analysis(run_dir=run_dir, runner=_NoRunRunner(), debate_rounds=1)

    _assert_resume_mismatch(exc, "--debate-rounds", "2", "1")
    assert _artifact_names(run_dir) == before_artifacts


def test_resume_rejects_mismatched_analysts_before_running(tmp_path):
    run_mock_analysis(
        ticker="SPY",
        trade_date="2026-01-15",
        output_dir=tmp_path,
        run_id="analysts-mismatch",
        language="Korean",
        depth="shallow",
        analysts="market,news",
    )
    run_dir = _run_dir(tmp_path, "analysts-mismatch")
    before_artifacts = _artifact_names(run_dir)

    with pytest.raises(ValueError) as exc:
        resume_shallow_analysis(run_dir=run_dir, runner=_NoRunRunner(), analysts="all")

    _assert_resume_mismatch(exc, "--analysts", "market_analyst,news_analyst", "market_analyst,sentiment_analyst,news_analyst,fundamentals_analyst")
    assert _artifact_names(run_dir) == before_artifacts


def test_resume_accepts_explicit_values_matching_manifest(tmp_path):
    run_mock_analysis(
        ticker="SPY",
        trade_date="2026-01-15",
        output_dir=tmp_path,
        run_id="matching-explicit-values",
        language="Korean",
        depth="shallow",
        analysts="market,news",
        debate_rounds=2,
        risk_rounds=2,
    )
    run_dir = _run_dir(tmp_path, "matching-explicit-values")
    _mark_steps_incomplete(
        run_dir,
        completed_steps={"07_risk_aggressive_round2", "08_risk_conservative_round2", "09_risk_neutral_round2", "portfolio_manager", "render_final_report"},
        output_keys={
            "07_risk_aggressive_round2",
            "08_risk_conservative_round2",
            "09_risk_neutral_round2",
            "risk_aggressive",
            "risk_conservative",
            "risk_neutral",
            "portfolio_manager",
            "final_report",
        },
    )

    result = resume_shallow_analysis(
        run_dir=run_dir,
        runner=MockRunner(),
        language="Korean",
        depth="shallow",
        analysts="market,news",
        debate_rounds=2,
        risk_rounds=2,
    )

    assert result.run_dir == run_dir
    state = _load_json(run_dir / "checkpoints/state.json")
    assert state["status"] == "completed"
    assert "07_risk_aggressive_round2" in state["completed_steps"]
    assert (run_dir / "outputs/07_risk_aggressive_round2.attempt1.json").exists()


def test_resume_defaults_old_manifest_missing_risk_rounds_to_one(tmp_path):
    run_mock_analysis(
        ticker="SPY",
        trade_date="2026-01-15",
        output_dir=tmp_path,
        run_id="old-manifest",
        language="Korean",
        depth="shallow",
    )
    run_dir = _run_dir(tmp_path, "old-manifest")
    manifest_path = run_dir / "manifest.json"
    manifest = _load_json(manifest_path)
    manifest.pop("risk_rounds", None)
    _write_json(manifest_path, manifest)
    _mark_steps_incomplete(
        run_dir,
        completed_steps={"portfolio_manager", "render_final_report"},
        output_keys={"portfolio_manager", "final_report"},
    )

    result = resume_shallow_analysis(run_dir=run_dir, runner=MockRunner(), language="Korean", depth="shallow")

    assert result.final_report_path == run_dir / "reports/final_report.md"
    state = _load_json(run_dir / "checkpoints/state.json")
    assert state["status"] == "completed"


def test_resume_cli_rejects_mismatched_debate_rounds(tmp_path):
    run_mock_analysis(
        ticker="SPY",
        trade_date="2026-01-15",
        output_dir=tmp_path,
        run_id="cli-debate-mismatch",
        language="Korean",
        depth="shallow",
        debate_rounds=2,
    )
    run_dir = _run_dir(tmp_path, "cli-debate-mismatch")

    result = CliRunner().invoke(app, ["resume", str(run_dir), "--runner", "mock", "--debate-rounds", "1"])

    assert result.exit_code != 0
    assert "--debate-rounds" in result.output
    assert "manifest has 2" in result.output
    assert "requested 1" in result.output
    assert "Start a new run" in result.output
