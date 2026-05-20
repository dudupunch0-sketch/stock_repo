from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from stock_agents.data.collector import collect_all_facts
from stock_agents.domain.enums import Role
from stock_agents.orchestration.checkpoints import CheckpointState, new_checkpoint_state, read_checkpoint, write_checkpoint
from stock_agents.orchestration.repair import build_repair_task
from stock_agents.orchestration.task_builder import build_agent_task, render_task
from stock_agents.orchestration.validator import extract_json_object, validate_output_for_role
from stock_agents.reporting.renderer import render_final_report
from stock_agents.runners.base import AgentRunner
from stock_agents.runners.mock import MockRunner
from stock_agents.schemas.outputs import PortfolioDecisionOutput
from stock_agents.schemas.tasks import AgentTask

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
    return run_shallow_analysis(
        ticker=ticker,
        trade_date=trade_date,
        runner=MockRunner(),
        output_dir=output_dir,
        run_id=run_id,
        language=language,
        depth=depth,
        timeout_seconds=60,
    )


def run_shallow_analysis(
    *,
    ticker: str,
    trade_date: str,
    runner: AgentRunner,
    output_dir: str | Path = "runs",
    run_id: str | None = None,
    language: str = "Korean",
    depth: Literal["shallow"] | str = "shallow",
    timeout_seconds: int = 60,
) -> PipelineResult:
    if depth != "shallow":
        raise ValueError("only shallow depth is implemented")

    collected = collect_all_facts(ticker=ticker, trade_date=trade_date, output_dir=output_dir, run_id=run_id)
    run_dir = collected.run_dir
    selected_run_id = run_dir.name
    state = new_checkpoint_state(run_id=selected_run_id, ticker=ticker, trade_date=trade_date)
    state.completed_steps.append("collect_facts")
    state.current_step = "market_analyst"
    write_checkpoint(run_dir, state)

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
        try:
            validated, output_path = _run_role_with_repair(
                task=task,
                task_text=task_text,
                runner=runner,
                run_dir=run_dir,
                timeout_seconds=timeout_seconds,
            )
        except Exception:
            state.status = "failed_validation"
            state.current_step = role.value
            write_checkpoint(run_dir, state)
            raise

        latest_path = run_dir / "outputs" / f"{task.task_id}.latest.json"
        latest_path.write_text(output_path.read_text(encoding="utf-8"), encoding="utf-8")

        state.completed_steps.append(role.value)
        state.outputs[role.value] = str(latest_path.relative_to(run_dir))
        completed_roles.append(role)
        if role is Role.PORTFOLIO_MANAGER:
            final_decision = validated  # type: ignore[assignment]

    if final_decision is None or not isinstance(final_decision, PortfolioDecisionOutput):
        raise RuntimeError("pipeline did not produce a portfolio decision")

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


def resume_shallow_analysis(
    *,
    run_dir: str | Path,
    runner: AgentRunner,
    language: str = "Korean",
    depth: Literal["shallow"] | str = "shallow",
    timeout_seconds: int = 60,
) -> PipelineResult:
    if depth != "shallow":
        raise ValueError("only shallow depth is implemented")

    selected_run_dir = Path(run_dir)
    state = read_checkpoint(selected_run_dir)
    completed_roles: list[Role] = []
    final_decision: PortfolioDecisionOutput | None = None

    for role in _SHALLOW_ROLE_SEQUENCE:
        task = build_agent_task(role=role, ticker=state.ticker, trade_date=state.trade_date, language=language)
        validated = _validated_latest_output(selected_run_dir, state, task)
        if role.value in state.completed_steps and validated is not None:
            completed_roles.append(role)
            if role is Role.PORTFOLIO_MANAGER:
                final_decision = validated  # type: ignore[assignment]
            continue

        next_attempt_number = _next_attempt_number(selected_run_dir, task.task_id)
        task = task.model_copy(update={"output_path": f"outputs/{task.task_id}.attempt{next_attempt_number}.json"})
        task_path = selected_run_dir / "tasks" / f"{task.task_id}.task.md"
        task_path.parent.mkdir(parents=True, exist_ok=True)
        task_text = render_task(task)
        task_path.write_text(task_text, encoding="utf-8")

        state.status = "running"
        state.current_step = role.value
        write_checkpoint(selected_run_dir, state)
        try:
            validated, output_path = _run_role_with_repair(
                task=task,
                task_text=task_text,
                runner=runner,
                run_dir=selected_run_dir,
                timeout_seconds=timeout_seconds,
                start_attempt_number=next_attempt_number,
            )
        except Exception:
            state.status = "failed_validation"
            state.current_step = role.value
            write_checkpoint(selected_run_dir, state)
            raise

        latest_path = selected_run_dir / "outputs" / f"{task.task_id}.latest.json"
        latest_path.write_text(output_path.read_text(encoding="utf-8"), encoding="utf-8")
        if role.value not in state.completed_steps:
            state.completed_steps.append(role.value)
        state.outputs[role.value] = str(latest_path.relative_to(selected_run_dir))
        completed_roles.append(role)
        if role is Role.PORTFOLIO_MANAGER:
            final_decision = validated  # type: ignore[assignment]

    if final_decision is None or not isinstance(final_decision, PortfolioDecisionOutput):
        raise RuntimeError("pipeline did not produce a portfolio decision")

    report_text = render_final_report(final_decision, language=language)
    final_report_path = selected_run_dir / "reports" / "final_report.md"
    final_report_path.parent.mkdir(parents=True, exist_ok=True)
    final_report_path.write_text(report_text, encoding="utf-8")

    manifest_path = selected_run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.setdefault("artifacts", {})["final_report"] = "reports/final_report.md"
    manifest["completed_roles"] = [role.value for role in completed_roles]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if "render_final_report" not in state.completed_steps:
        state.completed_steps.append("render_final_report")
    state.outputs["final_report"] = "reports/final_report.md"
    state.status = "completed"
    state.current_step = "complete"
    write_checkpoint(selected_run_dir, state)
    return PipelineResult(run_dir=selected_run_dir, final_report_path=final_report_path, completed_roles=completed_roles)


def _validated_latest_output(run_dir: Path, state: CheckpointState, task: AgentTask):
    relative_path = state.outputs.get(task.role.value, f"outputs/{task.task_id}.latest.json")
    output_path = run_dir / relative_path
    if not output_path.exists():
        return None
    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        return validate_output_for_role(task.role, payload)
    except Exception:
        return None


def _next_attempt_number(run_dir: Path, task_id: str) -> int:
    existing_attempts: list[int] = []
    for path in (run_dir / "outputs").glob(f"{task_id}.attempt*.*"):
        match = re.search(r"\.attempt(\d+)\.", path.name)
        if match is not None:
            existing_attempts.append(int(match.group(1)))
    if not existing_attempts:
        return 0
    return max(existing_attempts) + 1


def _run_role_with_repair(
    *,
    task: AgentTask,
    task_text: str,
    runner: AgentRunner,
    run_dir: Path,
    timeout_seconds: int,
    start_attempt_number: int = 0,
):
    attempt_number = start_attempt_number
    repairs_used = 0
    prompt = task_text

    while True:
        runner_result = runner.run(prompt, cwd=run_dir, timeout_seconds=timeout_seconds)
        raw_path = run_dir / "outputs" / f"{task.task_id}.attempt{attempt_number}.raw.txt"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        _write_text_with_trailing_newline(raw_path, runner_result.stdout)

        if runner_result.exit_code != 0:
            raise RuntimeError(
                f"runner {runner_result.runner} failed for {task.task_id} "
                f"with exit code {runner_result.exit_code}: {runner_result.stderr}"
            )

        try:
            payload = extract_json_object(runner_result.stdout)
            validated = validate_output_for_role(task.role, payload)
        except Exception as exc:
            if repairs_used >= task.max_repair_attempts:
                raise RuntimeError(
                    f"validation failed for {task.task_id} after {repairs_used + 1} repair attempt(s): {exc}"
                ) from exc
            repairs_used += 1
            attempt_number += 1
            prompt = build_repair_task(
                task=task,
                original_task_text=task_text,
                raw_output=runner_result.stdout,
                validation_error=str(exc),
                attempt_number=attempt_number,
            )
            repair_path = run_dir / "repairs" / f"{task.task_id}.attempt{attempt_number}.repair.task.md"
            repair_path.parent.mkdir(parents=True, exist_ok=True)
            repair_path.write_text(prompt, encoding="utf-8")
            continue

        output_path = run_dir / "outputs" / f"{task.task_id}.attempt{attempt_number}.json"
        output_path.write_text(validated.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return validated, output_path


def _write_text_with_trailing_newline(path: Path, text: str) -> None:
    suffix = "" if text.endswith("\n") else "\n"
    path.write_text(text + suffix, encoding="utf-8")
