from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from stock_agents.data.collector import collect_all_facts
from stock_agents.domain.enums import Role
from stock_agents.orchestration.checkpoints import new_checkpoint_state, write_checkpoint
from stock_agents.orchestration.task_builder import build_agent_task, render_task
from stock_agents.orchestration.validator import extract_json_object, validate_output_for_role
from stock_agents.reporting.renderer import render_final_report
from stock_agents.runners.mock import MockRunner
from stock_agents.schemas.outputs import PortfolioDecisionOutput

_SHALLOW_ROLE_SEQUENCE = (
    Role.MARKET_ANALYST,
    Role.NEWS_ANALYST,
    Role.BULL_RESEARCHER,
    Role.BEAR_RESEARCHER,
    Role.RESEARCH_MANAGER,
    Role.TRADER,
    Role.RISK_AGGRESSIVE,
    Role.RISK_CONSERVATIVE,
    Role.RISK_NEUTRAL,
    Role.PORTFOLIO_MANAGER,
)


class PipelineResult(BaseModel):
    run_dir: Path
    final_report_path: Path
    completed_roles: list[Role]


def run_mock_analysis(
    *,
    ticker: str,
    trade_date: str,
    output_dir: str | Path = "runs",
    run_id: str | None = None,
    language: str = "Korean",
    depth: Literal["shallow"] | str = "shallow",
) -> PipelineResult:
    if depth != "shallow":
        raise ValueError("only shallow depth is implemented for the mock Phase E pipeline")

    collected = collect_all_facts(ticker=ticker, trade_date=trade_date, output_dir=output_dir, run_id=run_id)
    run_dir = collected.run_dir
    selected_run_id = run_dir.name
    state = new_checkpoint_state(run_id=selected_run_id, ticker=ticker, trade_date=trade_date)
    state.completed_steps.append("collect_facts")
    state.current_step = "market_analyst"
    write_checkpoint(run_dir, state)

    runner = MockRunner()
    completed_roles: list[Role] = []
    final_decision: PortfolioDecisionOutput | None = None

    for role in _SHALLOW_ROLE_SEQUENCE:
        task = build_agent_task(role=role, ticker=ticker, trade_date=trade_date, language=language)
        task_path = run_dir / "tasks" / f"{task.task_id}.task.md"
        task_path.parent.mkdir(parents=True, exist_ok=True)
        task_text = render_task(task)
        task_path.write_text(task_text, encoding="utf-8")

        state.current_step = role.value
        write_checkpoint(run_dir, state)
        runner_result = runner.run(task_text, cwd=run_dir, timeout_seconds=60)
        raw_path = run_dir / "outputs" / f"{task.task_id}.attempt0.raw.txt"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(runner_result.stdout + "\n", encoding="utf-8")

        payload = extract_json_object(runner_result.stdout)
        validated = validate_output_for_role(role, payload)
        output_path = run_dir / "outputs" / f"{task.task_id}.attempt0.json"
        output_path.write_text(validated.model_dump_json(indent=2) + "\n", encoding="utf-8")
        latest_path = run_dir / "outputs" / f"{task.task_id}.latest.json"
        latest_path.write_text(output_path.read_text(encoding="utf-8"), encoding="utf-8")

        state.completed_steps.append(role.value)
        state.outputs[role.value] = str(latest_path.relative_to(run_dir))
        completed_roles.append(role)
        if role is Role.PORTFOLIO_MANAGER:
            final_decision = validated  # type: ignore[assignment]

    if final_decision is None or not isinstance(final_decision, PortfolioDecisionOutput):
        raise RuntimeError("mock pipeline did not produce a portfolio decision")

    report_text = render_final_report(final_decision, language=language)
    final_report_path = run_dir / "reports" / "final_report.md"
    final_report_path.parent.mkdir(parents=True, exist_ok=True)
    final_report_path.write_text(report_text, encoding="utf-8")

    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.setdefault("artifacts", {})["final_report"] = "reports/final_report.md"
    manifest["completed_roles"] = [role.value for role in completed_roles]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    state.completed_steps.append("render_final_report")
    state.outputs["final_report"] = "reports/final_report.md"
    state.status = "completed"
    state.current_step = "complete"
    write_checkpoint(run_dir, state)
    return PipelineResult(run_dir=run_dir, final_report_path=final_report_path, completed_roles=completed_roles)
