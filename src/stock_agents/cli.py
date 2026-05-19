from __future__ import annotations

from pathlib import Path

import typer

from stock_agents import __version__
from stock_agents.data.collector import collect_all_facts
from stock_agents.doctor import run_doctor
from stock_agents.domain.enums import Role
from stock_agents.orchestration.pipeline import run_mock_analysis
from stock_agents.orchestration.task_builder import build_agent_task, render_task
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
    smoke_runner: str = typer.Option("mock", "--smoke-runner", help="Runner smoke check: none, mock, or hermes."),
    hermes_executable: str = typer.Option("hermes", "--hermes-executable", help="Hermes executable to inspect."),
) -> None:
    """Check local runner prerequisites without requiring API keys."""
    try:
        typer.echo(run_doctor(smoke_runner=smoke_runner, hermes_executable=hermes_executable))
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
    runner: str = typer.Option("mock", "--runner", help="Runner name: mock or hermes."),
    provider: str | None = typer.Option(None, "--provider", help="Optional Hermes provider override."),
    model: str | None = typer.Option(None, "--model", help="Optional Hermes model override."),
    hermes_executable: str = typer.Option("hermes", "--hermes-executable", help="Hermes executable for --runner hermes."),
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
    else:
        raise typer.BadParameter("runner must be one of: mock, hermes")

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
def validate() -> None:
    """Validate raw runner JSON output. Placeholder for the next milestone."""
    typer.echo("validate command placeholder: schema validator is available as a Python API.")


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
    runner: str = typer.Option("mock", "--runner", help="Runner name. Only mock is implemented in Phase E."),
    language: str = typer.Option("Korean", "--language", help="Output language for human-readable fields."),
    depth: str = typer.Option("shallow", "--depth", help="Pipeline depth. Only shallow is implemented in Phase E."),
    output_dir: Path = typer.Option(Path("runs"), "--output-dir", help="Base directory for run artifacts."),
    run_id: str | None = typer.Option(None, "--run-id", help="Optional deterministic run id for tests/reproducibility."),
) -> None:
    """Run the mock full analysis pipeline."""
    if runner != "mock":
        raise typer.BadParameter("only --runner mock is implemented in Phase E")
    try:
        result = run_mock_analysis(
            ticker=ticker,
            trade_date=date,
            output_dir=output_dir,
            run_id=run_id,
            language=language,
            depth=depth,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(str(result.run_dir))
    typer.echo(str(result.final_report_path))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
