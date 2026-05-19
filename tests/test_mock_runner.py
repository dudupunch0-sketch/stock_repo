import json

from stock_agents.domain.enums import Role
from stock_agents.orchestration.task_builder import render_task
from stock_agents.orchestration.validator import validate_output_for_role
from stock_agents.runners.mock import MockRunner
from stock_agents.schemas.tasks import AgentTask


def _task(role: Role, schema_name: str, task_id: str = "01_task"):
    return AgentTask(
        task_id=task_id,
        role=role,
        ticker="SPY",
        trade_date="2026-01-15",
        language="Korean",
        input_paths=["inputs/market_facts.json"],
        output_schema_name=schema_name,
        output_path=f"outputs/{task_id}.attempt0.json",
        objective="Produce a valid fixture output.",
        evidence_rules=["Cite inputs."],
        forbidden_claims=["No guaranteed returns."],
    )


def test_mock_runner_returns_valid_analyst_json_for_task_prompt(tmp_path):
    task = _task(Role.MARKET_ANALYST, "AnalystOutput", "01_market_analyst")
    prompt = render_task(task)

    result = MockRunner().run(prompt, cwd=tmp_path, timeout_seconds=5)
    payload = json.loads(result.stdout)
    output = validate_output_for_role(Role.MARKET_ANALYST, payload)

    assert result.exit_code == 0
    assert output.role == Role.MARKET_ANALYST
    assert output.ticker == "SPY"
    assert output.report_markdown


def test_mock_runner_returns_portfolio_disclaimer_flag(tmp_path):
    task = _task(Role.PORTFOLIO_MANAGER, "PortfolioDecisionOutput", "10_portfolio_manager")
    prompt = render_task(task)

    result = MockRunner().run(prompt, cwd=tmp_path, timeout_seconds=5)
    payload = json.loads(result.stdout)
    output = validate_output_for_role(Role.PORTFOLIO_MANAGER, payload)

    assert output.not_financial_advice is True
    assert output.rating.value == "Hold"
