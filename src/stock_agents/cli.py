from __future__ import annotations

import json
from pathlib import Path

import typer

from stock_agents import __version__
from stock_agents.data.collector import collect_all_facts
from stock_agents.doctor import run_doctor
from stock_agents.domain.enums import Role
from stock_agents.orchestration.pipeline import resume_shallow_analysis, run_mock_analysis, run_shallow_analysis
from stock_agents.orchestration.task_builder import build_agent_task, render_task
from stock_agents.orchestration.validator import extract_json_object, validate_output_for_role
from stock_agents.runners.codex import CodexRunner
from stock_agents.runners.hermes import HermesRunner
from stock_agents.runners.mock import MockRunner

app = typer.Typer(
    help=(
        "TradingAgents file-handoff orchestrator for Hermes/Codex/Mock runners. "
        "Build task packages, validate JSON outputs, and run deterministic local mocks."
    ),
    no_args_is_help=True,
    invoke_without_command=True,
)


@app.callback()
def _main(
    version: bool = typer.Option(False, "--version", help="Show the stock-agents version and exit."),
) -> None:
    if version:
        typer.echo(__version__)
        raise typer.Exit()


@app.command()
def doctor(
    smoke_runner: str = typer.Option("mock", "--smoke-runner", help="Runner smoke check: none, mock, hermes, or codex."),
    hermes_executable: str = typer.Option("hermes", "--hermes-executable", help="Hermes executable to inspect."),
    codex_executable: str = typer.Option("codex", "--codex-executable", help="Codex executable to inspect."),
) -> None:
    """Check local runner prerequisites without requiring API keys."""
    try:
        typer.echo(
            run_doctor(
                smoke_runner=smoke_runner,
                hermes_executable=hermes_executable,
                codex_executable=codex_executable,
            )
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command("build-tasks")
def build_tasks(
    ticker: str = typer.Argument(..., help="Ticker symbol, e.g. SPY."),
    date: str = typer.Option(..., "--date", help="Trade date in YYYY-MM-DD format."),
    role: Role = typer.Option(Role.MARKET_ANALYST, "--role", help="Role task to render."),
    language: str = typer.Option("Korean", "--language", help="Output language for human-readable fields."),
) -> None:
    """Render one file-handoff task package to stdout."""
    task = build_agent_task(role=role, ticker=ticker, trade_date=date, language=language)
    typer.echo(render_task(task))


@app.command("run-task")
def run_task(
    task_file: Path = typer.Argument(..., help="Rendered task markdown file."),
    runner: str = typer.Option("mock", "--runner", help="Runner name: mock, hermes, or codex."),
    provider: str | None = typer.Option(None, "--provider", help="Optional Hermes provider override."),
    model: str | None = typer.Option(None, "--model", help="Optional Hermes/Codex model override."),
    hermes_executable: str = typer.Option("hermes", "--hermes-executable", help="Hermes executable for --runner hermes."),
    codex_executable: str = typer.Option("codex", "--codex-executable", help="Codex executable for --runner codex."),
    reasoning_effort: str = typer.Option("medium", "--reasoning-effort", help="Codex model reasoning effort."),
    timeout_seconds: int = typer.Option(60, "--timeout-seconds", min=1, help="Runner timeout in seconds."),
) -> None:
    """Run a rendered task package with a local runner."""
    prompt = task_file.read_text(encoding="utf-8")
    runner_cwd = _runner_cwd_for_task(task_file)
    if runner == "mock":
        result = MockRunner().run(prompt, cwd=runner_cwd, timeout_seconds=timeout_seconds)
    elif runner == "hermes":
        result = HermesRunner(executable=hermes_executable, provider=provider, model=model).run(
            prompt,
            cwd=runner_cwd,
            timeout_seconds=timeout_seconds,
        )
    elif runner == "codex":
        result = CodexRunner(
            executable=codex_executable,
            model=model or "gpt-5.5",
            model_reasoning_effort=reasoning_effort,
        ).run(
            prompt,
            cwd=runner_cwd,
            timeout_seconds=timeout_seconds,
        )
    else:
        raise typer.BadParameter("runner must be one of: mock, hermes, codex")

    if result.stderr:
        typer.echo(result.stderr, err=True)
    typer.echo(result.stdout)
    if result.exit_code != 0:
        raise typer.Exit(result.exit_code)

def _runner_cwd_for_task(task_file: Path) -> Path:
    resolved_task_file = task_file.resolve()
    if resolved_task_file.parent.name == "tasks":
        return resolved_task_file.parent.parent
    return resolved_task_file.parent


@app.command()
def validate(
    raw_output: Path = typer.Argument(..., help="Raw runner output text file to validate."),
    role: Role = typer.Option(..., "--role", help="Expected role schema for the output."),
    output: Path | None = typer.Option(None, "--output", help="Optional path for canonical validated JSON."),
) -> None:
    """Validate raw runner output and emit canonical JSON."""
    try:
        raw_text = raw_output.read_text(encoding="utf-8")
        payload = extract_json_object(raw_text)
        validated = validate_output_for_role(role, payload)
    except FileNotFoundError as exc:
        raise typer.BadParameter(f"raw output file not found: {raw_output}") from exc
    except Exception as exc:
        typer.echo(f"validation failed: {exc}", err=True)
        raise typer.Exit(1) from exc

    canonical_json = validated.model_dump_json(indent=2) + "\n"
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(canonical_json, encoding="utf-8")
        typer.echo(str(output))
        return
    typer.echo(canonical_json, nl=False)


@app.command("show-run")
def show_run(
    run_dir: Path = typer.Argument(..., help="Run artifact directory to inspect."),
) -> None:
    """Summarize a run checkpoint and its current output artifacts."""
    state_path = run_dir / "checkpoints" / "state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise typer.BadParameter(f"checkpoint not found: {state_path}") from exc

    typer.echo(f"Run: {state['run_id']}")
    typer.echo(f"Ticker: {state['ticker']}")
    typer.echo(f"Trade date: {state['trade_date']}")
    typer.echo(f"Status: {state['status']}")
    typer.echo(f"Current step: {state.get('current_step')}")
    typer.echo("Completed steps:")
    for step in state.get("completed_steps", []):
        typer.echo(f"- {step}")
    typer.echo("Outputs:")
    for name, relative_path in state.get("outputs", {}).items():
        typer.echo(f"- {name}: {relative_path}")
    final_report = state.get("outputs", {}).get("final_report")
    if final_report:
        typer.echo(f"Final report: {run_dir / final_report}")


@app.command()
def collect(
    ticker: str = typer.Argument(..., help="Ticker symbol, e.g. SPY."),
    date: str = typer.Option(..., "--date", help="Trade date in YYYY-MM-DD format."),
    output_dir: Path = typer.Option(Path("runs"), "--output-dir", help="Base directory for run artifacts."),
    run_id: str | None = typer.Option(None, "--run-id", help="Optional deterministic run id for tests/reproducibility."),
) -> None:
    """Collect minimum fact artifacts for a run directory."""
    try:
        collected = collect_all_facts(ticker=ticker, trade_date=date, output_dir=output_dir, run_id=run_id)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(str(collected.run_dir))


@app.command()
def analyze(
    ticker: str = typer.Argument(..., help="Ticker symbol, e.g. SPY."),
    date: str = typer.Option(..., "--date", help="Trade date in YYYY-MM-DD format."),
    runner: str = typer.Option("mock", "--runner", help="Runner name: mock, hermes, or codex."),
    provider: str | None = typer.Option(None, "--provider", help="Optional Hermes provider override."),
    model: str | None = typer.Option(None, "--model", help="Optional Hermes/Codex model override."),
    hermes_executable: str = typer.Option("hermes", "--hermes-executable", help="Hermes executable for --runner hermes."),
    codex_executable: str = typer.Option("codex", "--codex-executable", help="Codex executable for --runner codex."),
    reasoning_effort: str = typer.Option("medium", "--reasoning-effort", help="Codex model reasoning effort."),
    timeout_seconds: int = typer.Option(60, "--timeout-seconds", min=1, help="Per-role runner timeout in seconds."),
    language: str = typer.Option("Korean", "--language", help="Output language for human-readable fields."),
    depth: str = typer.Option("shallow", "--depth", help="Pipeline depth. Only shallow is implemented."),
    analysts: str = typer.Option("market,news", "--analysts", help="Comma-separated analyst roles: market,news,sentiment,fundamentals, or all."),
    debate_rounds: int = typer.Option(1, "--debate-rounds", min=1, help="Number of bull/bear research debate rounds."),
    risk_rounds: int = typer.Option(1, "--risk-rounds", min=1, help="Number of risk-team debate rounds."),
    output_dir: Path = typer.Option(Path("runs"), "--output-dir", help="Base directory for run artifacts."),
    run_id: str | None = typer.Option(None, "--run-id", help="Optional deterministic run id for tests/reproducibility."),
) -> None:
    """Run the shallow analysis pipeline."""
    try:
        if runner == "mock":
            result = run_mock_analysis(
                ticker=ticker,
                trade_date=date,
                output_dir=output_dir,
                run_id=run_id,
                language=language,
                depth=depth,
                analysts=analysts,
                debate_rounds=debate_rounds,
                risk_rounds=risk_rounds,
            )
        elif runner == "hermes":
            result = run_shallow_analysis(
                ticker=ticker,
                trade_date=date,
                runner=HermesRunner(executable=hermes_executable, provider=provider, model=model),
                output_dir=output_dir,
                run_id=run_id,
                language=language,
                depth=depth,
                timeout_seconds=timeout_seconds,
                analysts=analysts,
                debate_rounds=debate_rounds,
                risk_rounds=risk_rounds,
            )
        elif runner == "codex":
            result = run_shallow_analysis(
                ticker=ticker,
                trade_date=date,
                runner=CodexRunner(
                    executable=codex_executable,
                    model=model or "gpt-5.5",
                    model_reasoning_effort=reasoning_effort,
                ),
                output_dir=output_dir,
                run_id=run_id,
                language=language,
                depth=depth,
                timeout_seconds=timeout_seconds,
                analysts=analysts,
                debate_rounds=debate_rounds,
                risk_rounds=risk_rounds,
            )
        else:
            raise typer.BadParameter("runner must be one of: mock, hermes, codex")
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(str(result.run_dir))
    typer.echo(str(result.final_report_path))


@app.command()
def resume(
    run_dir: Path = typer.Argument(..., help="Existing run artifact directory to resume."),
    runner: str = typer.Option("mock", "--runner", help="Runner name: mock, hermes, or codex."),
    provider: str | None = typer.Option(None, "--provider", help="Optional Hermes provider override."),
    model: str | None = typer.Option(None, "--model", help="Optional Hermes/Codex model override."),
    hermes_executable: str = typer.Option("hermes", "--hermes-executable", help="Hermes executable for --runner hermes."),
    codex_executable: str = typer.Option("codex", "--codex-executable", help="Codex executable for --runner codex."),
    reasoning_effort: str = typer.Option("medium", "--reasoning-effort", help="Codex model reasoning effort."),
    timeout_seconds: int = typer.Option(60, "--timeout-seconds", min=1, help="Per-role runner timeout in seconds."),
    language: str = typer.Option("Korean", "--language", help="Output language for human-readable fields."),
    depth: str = typer.Option("shallow", "--depth", help="Pipeline depth. Only shallow is implemented."),
    analysts: str | None = typer.Option(None, "--analysts", help="Comma-separated analyst roles used by the run; omit to reuse manifest/default."),
    debate_rounds: int | None = typer.Option(None, "--debate-rounds", min=1, help="Number of bull/bear research debate rounds; omit to reuse manifest/default."),
    risk_rounds: int | None = typer.Option(None, "--risk-rounds", min=1, help="Number of risk-team debate rounds; omit to reuse manifest/default."),
) -> None:
    """Resume an existing shallow analysis run from its checkpoint."""
    try:
        if runner == "mock":
            selected_runner = MockRunner()
        elif runner == "hermes":
            selected_runner = HermesRunner(executable=hermes_executable, provider=provider, model=model)
        elif runner == "codex":
            selected_runner = CodexRunner(
                executable=codex_executable,
                model=model or "gpt-5.5",
                model_reasoning_effort=reasoning_effort,
            )
        else:
            raise typer.BadParameter("runner must be one of: mock, hermes, codex")
        result = resume_shallow_analysis(
            run_dir=run_dir,
            runner=selected_runner,
            language=language,
            depth=depth,
            timeout_seconds=timeout_seconds,
            analysts=analysts,
            debate_rounds=debate_rounds,
            risk_rounds=risk_rounds,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(str(result.run_dir))
    typer.echo(str(result.final_report_path))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
