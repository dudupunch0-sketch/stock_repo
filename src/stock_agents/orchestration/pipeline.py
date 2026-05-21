from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from stock_agents.data.collector import collect_all_facts
from stock_agents.domain.enums import Role
from stock_agents.orchestration.checkpoints import CheckpointState, new_checkpoint_state, read_checkpoint, write_checkpoint
from stock_agents.orchestration.repair import build_repair_task
from stock_agents.orchestration.task_builder import ROLE_TASK_SPECS, build_agent_task, render_task
from stock_agents.orchestration.validator import extract_json_object, validate_output_for_role
from stock_agents.reporting.renderer import render_final_report
from stock_agents.runners.base import AgentRunner
from stock_agents.runners.mock import MockRunner
from stock_agents.schemas.outputs import PortfolioDecisionOutput
from stock_agents.schemas.tasks import AgentTask

_DEFAULT_ANALYST_ROLES = (Role.MARKET_ANALYST, Role.NEWS_ANALYST)
_ALL_ANALYST_ROLES = (
    Role.MARKET_ANALYST,
    Role.SENTIMENT_ANALYST,
    Role.NEWS_ANALYST,
    Role.FUNDAMENTALS_ANALYST,
)
_RESEARCH_AND_TRADER_ROLE_SEQUENCE = (
    Role.RESEARCH_MANAGER,
    Role.TRADER,
)
_RISK_ROLE_SEQUENCE = (
    Role.RISK_AGGRESSIVE,
    Role.RISK_CONSERVATIVE,
    Role.RISK_NEUTRAL,
)
_POST_RISK_ROLE_SEQUENCE = (
    Role.PORTFOLIO_MANAGER,
)
MIN_DEBATE_ROUNDS = 1
MAX_DEBATE_ROUNDS = 3
MIN_RISK_ROUNDS = 1
MAX_RISK_ROUNDS = 3
_ANALYST_ALIASES = {
    "market": Role.MARKET_ANALYST,
    "market_analyst": Role.MARKET_ANALYST,
    "sentiment": Role.SENTIMENT_ANALYST,
    "sentiment_analyst": Role.SENTIMENT_ANALYST,
    "news": Role.NEWS_ANALYST,
    "news_analyst": Role.NEWS_ANALYST,
    "fundamental": Role.FUNDAMENTALS_ANALYST,
    "fundamentals": Role.FUNDAMENTALS_ANALYST,
    "fundamentals_analyst": Role.FUNDAMENTALS_ANALYST,
}
AnalystSelection = str | Sequence[str | Role] | None


@dataclass(frozen=True)
class PipelineStep:
    role: Role
    round_number: int | None = None


class PipelineResult(BaseModel):
    run_dir: Path
    final_report_path: Path
    completed_roles: list[Role]


def resolve_analyst_roles(analysts: AnalystSelection = None) -> tuple[Role, ...]:
    if analysts is None:
        return _DEFAULT_ANALYST_ROLES

    if isinstance(analysts, str):
        tokens = [token.strip().lower() for token in analysts.split(",") if token.strip()]
    else:
        tokens = [token.value if isinstance(token, Role) else str(token).strip().lower() for token in analysts]

    if not tokens or tokens == ["default"]:
        return _DEFAULT_ANALYST_ROLES
    if "all" in tokens:
        if len(tokens) != 1:
            raise ValueError("analyst selector 'all' cannot be combined with explicit analyst names")
        return _ALL_ANALYST_ROLES

    roles: list[Role] = []
    for token in tokens:
        role = _ANALYST_ALIASES.get(token)
        if role is None:
            valid = ", ".join(sorted({"all", "market", "sentiment", "news", "fundamentals"}))
            raise ValueError(f"unknown analyst '{token}'. Valid analysts: {valid}")
        if role not in roles:
            roles.append(role)
    return tuple(roles)


def resolve_debate_rounds(debate_rounds: int) -> int:
    if not MIN_DEBATE_ROUNDS <= debate_rounds <= MAX_DEBATE_ROUNDS:
        raise ValueError(f"debate_rounds must be between {MIN_DEBATE_ROUNDS} and {MAX_DEBATE_ROUNDS}")
    return debate_rounds


def resolve_risk_rounds(risk_rounds: int) -> int:
    if not MIN_RISK_ROUNDS <= risk_rounds <= MAX_RISK_ROUNDS:
        raise ValueError(f"risk_rounds must be between {MIN_RISK_ROUNDS} and {MAX_RISK_ROUNDS}")
    return risk_rounds


def _steps_for_analysis(
    analyst_roles: tuple[Role, ...],
    *,
    debate_rounds: int,
    risk_rounds: int,
) -> tuple[PipelineStep, ...]:
    rounds = resolve_debate_rounds(debate_rounds)
    risk_round_count = resolve_risk_rounds(risk_rounds)
    steps = [PipelineStep(role=role) for role in analyst_roles]
    if rounds == 1:
        steps.extend((PipelineStep(role=Role.BULL_RESEARCHER), PipelineStep(role=Role.BEAR_RESEARCHER)))
    else:
        for round_number in range(1, rounds + 1):
            steps.extend(
                (
                    PipelineStep(role=Role.BULL_RESEARCHER, round_number=round_number),
                    PipelineStep(role=Role.BEAR_RESEARCHER, round_number=round_number),
                )
            )
    steps.extend(PipelineStep(role=role) for role in _RESEARCH_AND_TRADER_ROLE_SEQUENCE)
    if risk_round_count == 1:
        steps.extend(PipelineStep(role=role) for role in _RISK_ROLE_SEQUENCE)
    else:
        for round_number in range(1, risk_round_count + 1):
            steps.extend(PipelineStep(role=role, round_number=round_number) for role in _RISK_ROLE_SEQUENCE)
    steps.extend(PipelineStep(role=role) for role in _POST_RISK_ROLE_SEQUENCE)
    return tuple(steps)


def _task_for_step(
    *,
    step: PipelineStep,
    ticker: str,
    trade_date: str,
    language: str,
    analyst_roles: tuple[Role, ...],
    debate_rounds: int,
    risk_rounds: int,
) -> AgentTask:
    role = step.role
    task = build_agent_task(role=role, ticker=ticker, trade_date=trade_date, language=language)
    if role in {Role.BULL_RESEARCHER, Role.BEAR_RESEARCHER}:
        dependency_output_paths = [
            f"outputs/{ROLE_TASK_SPECS[analyst_role].task_id}.latest.json"
            for analyst_role in analyst_roles
        ]
        updates: dict[str, object] = {"dependency_output_paths": dependency_output_paths}
        if step.round_number is not None:
            task_id = f"{task.task_id}_round{step.round_number}"
            if step.round_number > 1:
                previous_round = step.round_number - 1
                dependency_output_paths.extend(
                    (
                        f"outputs/03_bull_researcher_round{previous_round}.latest.json",
                        f"outputs/04_bear_researcher_round{previous_round}.latest.json",
                    )
                )
            updates.update(
                {
                    "task_id": task_id,
                    "output_path": f"outputs/{task_id}.attempt0.json",
                    "objective": f"Debate round {step.round_number} of {debate_rounds}. {task.objective}",
                }
            )
        return task.model_copy(update=updates)
    if role is Role.RESEARCH_MANAGER and debate_rounds > 1:
        return task.model_copy(
            update={
                "dependency_output_paths": [
                    f"outputs/03_bull_researcher_round{debate_rounds}.latest.json",
                    f"outputs/04_bear_researcher_round{debate_rounds}.latest.json",
                ]
            }
        )
    if role in _RISK_ROLE_SEQUENCE:
        dependency_output_paths = list(task.dependency_output_paths)
        risk_updates: dict[str, object] = {"dependency_output_paths": dependency_output_paths}
        if step.round_number is not None:
            task_id = f"{task.task_id}_round{step.round_number}"
            if step.round_number > 1:
                previous_round = step.round_number - 1
                dependency_output_paths.extend(
                    f"outputs/{ROLE_TASK_SPECS[risk_role].task_id}_round{previous_round}.latest.json"
                    for risk_role in _RISK_ROLE_SEQUENCE
                )
            risk_updates.update(
                {
                    "task_id": task_id,
                    "output_path": f"outputs/{task_id}.attempt0.json",
                    "objective": f"Risk debate round {step.round_number} of {risk_rounds}. {task.objective}",
                }
            )
        return task.model_copy(update=risk_updates)
    if role is Role.PORTFOLIO_MANAGER and risk_rounds > 1:
        return task.model_copy(
            update={
                "dependency_output_paths": [
                    "outputs/05_research_manager.latest.json",
                    "outputs/06_trader.latest.json",
                    *(
                        f"outputs/{ROLE_TASK_SPECS[risk_role].task_id}_round{risk_rounds}.latest.json"
                        for risk_role in _RISK_ROLE_SEQUENCE
                    ),
                ]
            }
        )
    return task


def _record_run_options_in_manifest(
    run_dir: Path,
    *,
    analyst_roles: tuple[Role, ...],
    debate_rounds: int,
    risk_rounds: int,
) -> None:
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["analyst_roles"] = [role.value for role in analyst_roles]
    manifest["debate_rounds"] = debate_rounds
    manifest["risk_rounds"] = risk_rounds
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _resume_manifest(run_dir: Path) -> dict:
    manifest_path = run_dir / "manifest.json"
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def _manifest_analyst_roles(manifest: dict) -> tuple[Role, ...]:
    saved_analysts = manifest.get("analyst_roles")
    if not saved_analysts:
        return _DEFAULT_ANALYST_ROLES
    return resolve_analyst_roles(saved_analysts)


def _manifest_debate_rounds(manifest: dict) -> int:
    return resolve_debate_rounds(int(manifest.get("debate_rounds", 1)))


def _manifest_risk_rounds(manifest: dict) -> int:
    return resolve_risk_rounds(int(manifest.get("risk_rounds", 1)))


def _format_analyst_roles(roles: tuple[Role, ...]) -> str:
    return ",".join(role.value for role in roles)


def _raise_resume_option_mismatch(*, option: str, manifest_value: str, requested_value: str) -> None:
    raise ValueError(
        f"resume option mismatch for {option}: manifest has {manifest_value}, requested {requested_value}. "
        "Start a new run to change graph-shaping options."
    )


def _analyst_roles_for_resume(run_dir: Path, analysts: AnalystSelection) -> tuple[Role, ...]:
    manifest_roles = _manifest_analyst_roles(_resume_manifest(run_dir))
    if analysts is None:
        return manifest_roles
    requested_roles = resolve_analyst_roles(analysts)
    if requested_roles != manifest_roles:
        _raise_resume_option_mismatch(
            option="--analysts",
            manifest_value=_format_analyst_roles(manifest_roles),
            requested_value=_format_analyst_roles(requested_roles),
        )
    return manifest_roles


def _debate_rounds_for_resume(run_dir: Path, debate_rounds: int | None) -> int:
    manifest_rounds = _manifest_debate_rounds(_resume_manifest(run_dir))
    if debate_rounds is None:
        return manifest_rounds
    requested_rounds = resolve_debate_rounds(debate_rounds)
    if requested_rounds != manifest_rounds:
        _raise_resume_option_mismatch(
            option="--debate-rounds",
            manifest_value=str(manifest_rounds),
            requested_value=str(requested_rounds),
        )
    return manifest_rounds


def _risk_rounds_for_resume(run_dir: Path, risk_rounds: int | None) -> int:
    manifest_rounds = _manifest_risk_rounds(_resume_manifest(run_dir))
    if risk_rounds is None:
        return manifest_rounds
    requested_rounds = resolve_risk_rounds(risk_rounds)
    if requested_rounds != manifest_rounds:
        _raise_resume_option_mismatch(
            option="--risk-rounds",
            manifest_value=str(manifest_rounds),
            requested_value=str(requested_rounds),
        )
    return manifest_rounds


def _checkpoint_key(task: AgentTask) -> str:
    if task.task_id == ROLE_TASK_SPECS[task.role].task_id:
        return task.role.value
    return task.task_id


def run_mock_analysis(
    *,
    ticker: str,
    trade_date: str,
    output_dir: str | Path = "runs",
    run_id: str | None = None,
    language: str = "Korean",
    depth: Literal["shallow"] | str = "shallow",
    analysts: AnalystSelection = None,
    debate_rounds: int = 1,
    risk_rounds: int = 1,
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
        analysts=analysts,
        debate_rounds=debate_rounds,
        risk_rounds=risk_rounds,
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
    analysts: AnalystSelection = None,
    debate_rounds: int = 1,
    risk_rounds: int = 1,
) -> PipelineResult:
    if depth != "shallow":
        raise ValueError("only shallow depth is implemented")
    analyst_roles = resolve_analyst_roles(analysts)
    debate_round_count = resolve_debate_rounds(debate_rounds)
    risk_round_count = resolve_risk_rounds(risk_rounds)
    steps = _steps_for_analysis(
        analyst_roles,
        debate_rounds=debate_round_count,
        risk_rounds=risk_round_count,
    )

    collected = collect_all_facts(ticker=ticker, trade_date=trade_date, output_dir=output_dir, run_id=run_id)
    run_dir = collected.run_dir
    _record_run_options_in_manifest(
        run_dir,
        analyst_roles=analyst_roles,
        debate_rounds=debate_round_count,
        risk_rounds=risk_round_count,
    )
    selected_run_id = run_dir.name
    state = new_checkpoint_state(run_id=selected_run_id, ticker=ticker, trade_date=trade_date)
    state.completed_steps.append("collect_facts")
    state.current_step = analyst_roles[0].value
    write_checkpoint(run_dir, state)

    completed_roles: list[Role] = []
    final_decision: PortfolioDecisionOutput | None = None

    for step in steps:
        role = step.role
        task = _task_for_step(
            step=step,
            ticker=ticker,
            trade_date=trade_date,
            language=language,
            analyst_roles=analyst_roles,
            debate_rounds=debate_round_count,
            risk_rounds=risk_round_count,
        )
        step_key = _checkpoint_key(task)
        task_path = run_dir / "tasks" / f"{task.task_id}.task.md"
        task_path.parent.mkdir(parents=True, exist_ok=True)
        task_text = render_task(task)
        task_path.write_text(task_text, encoding="utf-8")

        state.current_step = step_key
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
            state.current_step = step_key
            write_checkpoint(run_dir, state)
            raise

        latest_path = run_dir / "outputs" / f"{task.task_id}.latest.json"
        latest_path.write_text(output_path.read_text(encoding="utf-8"), encoding="utf-8")

        if step_key not in state.completed_steps:
            state.completed_steps.append(step_key)
        relative_latest_path = str(latest_path.relative_to(run_dir))
        state.outputs[step_key] = relative_latest_path
        state.outputs[role.value] = relative_latest_path
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
    manifest["analyst_roles"] = [role.value for role in analyst_roles]
    manifest["debate_rounds"] = debate_round_count
    manifest["risk_rounds"] = risk_round_count
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
    analysts: AnalystSelection = None,
    debate_rounds: int | None = None,
    risk_rounds: int | None = None,
) -> PipelineResult:
    if depth != "shallow":
        raise ValueError("only shallow depth is implemented")

    selected_run_dir = Path(run_dir)
    analyst_roles = _analyst_roles_for_resume(selected_run_dir, analysts)
    debate_round_count = _debate_rounds_for_resume(selected_run_dir, debate_rounds)
    risk_round_count = _risk_rounds_for_resume(selected_run_dir, risk_rounds)
    steps = _steps_for_analysis(
        analyst_roles,
        debate_rounds=debate_round_count,
        risk_rounds=risk_round_count,
    )
    state = read_checkpoint(selected_run_dir)
    completed_roles: list[Role] = []
    final_decision: PortfolioDecisionOutput | None = None

    for step in steps:
        role = step.role
        task = _task_for_step(
            step=step,
            ticker=state.ticker,
            trade_date=state.trade_date,
            language=language,
            analyst_roles=analyst_roles,
            debate_rounds=debate_round_count,
            risk_rounds=risk_round_count,
        )
        step_key = _checkpoint_key(task)
        validated = _validated_latest_output(selected_run_dir, state, task)
        if step_key in state.completed_steps and validated is not None:
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
        state.current_step = step_key
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
            state.current_step = step_key
            write_checkpoint(selected_run_dir, state)
            raise

        latest_path = selected_run_dir / "outputs" / f"{task.task_id}.latest.json"
        latest_path.write_text(output_path.read_text(encoding="utf-8"), encoding="utf-8")
        if step_key not in state.completed_steps:
            state.completed_steps.append(step_key)
        relative_latest_path = str(latest_path.relative_to(selected_run_dir))
        state.outputs[step_key] = relative_latest_path
        state.outputs[role.value] = relative_latest_path
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
    manifest["analyst_roles"] = [role.value for role in analyst_roles]
    manifest["debate_rounds"] = debate_round_count
    manifest["risk_rounds"] = risk_round_count
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if "render_final_report" not in state.completed_steps:
        state.completed_steps.append("render_final_report")
    state.outputs["final_report"] = "reports/final_report.md"
    state.status = "completed"
    state.current_step = "complete"
    write_checkpoint(selected_run_dir, state)
    return PipelineResult(run_dir=selected_run_dir, final_report_path=final_report_path, completed_roles=completed_roles)


def _validated_latest_output(run_dir: Path, state: CheckpointState, task: AgentTask):
    relative_path = state.outputs.get(_checkpoint_key(task), f"outputs/{task.task_id}.latest.json")
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
