from __future__ import annotations

from pathlib import Path

import typer

from stock_agents import __version__
from stock_agents.domain.enums import Role
from stock_agents.orchestration.task_builder import build_agent_task, render_task
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
def doctor() -> None:
    """Check local runner prerequisites without requiring API keys."""
    typer.echo("stock-agents doctor: mock runner available; Hermes/Codex checks are not implemented yet.")


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
    runner: str = typer.Option("mock", "--runner", help="Runner name. Only mock is implemented in this milestone."),
) -> None:
    """Run a rendered task package with a local runner."""
    if runner != "mock":
        raise typer.BadParameter("only --runner mock is implemented in Phase A-C")
    result = MockRunner().run(task_file.read_text(), cwd=task_file.parent, timeout_seconds=60)
    typer.echo(result.stdout)


@app.command()
def validate() -> None:
    """Validate raw runner JSON output. Placeholder for the next milestone."""
    typer.echo("validate command placeholder: schema validator is available as a Python API.")


@app.command()
def collect() -> None:
    """Collect deterministic market facts. Placeholder for Phase D."""
    typer.echo("collect command placeholder: data collection starts in Phase D.")


@app.command()
def analyze() -> None:
    """Run the full analysis pipeline. Placeholder for Phase E."""
    typer.echo("analyze command placeholder: mock pipeline starts in Phase E.")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
