from pathlib import Path

from stock_agents.domain.enums import Role
from stock_agents.orchestration.task_builder import render_task
from stock_agents.schemas.tasks import AgentTask


def _task():
    return AgentTask(
        task_id="01_market_analyst",
        role=Role.MARKET_ANALYST,
        ticker="SPY",
        trade_date="2026-01-15",
        language="Korean",
        input_paths=["inputs/market_facts.json", "inputs/technical_facts.json"],
        output_schema_name="AnalystOutput",
        output_path="outputs/01_market_analyst.attempt0.json",
        objective="기술적 시장 신호를 근거 기반으로 분석한다.",
        evidence_rules=["Every signal should cite the provided facts."],
        forbidden_claims=["Do not guarantee future returns."],
    )


def test_render_task_includes_file_handoff_contract_sections():
    task_markdown = render_task(_task(), input_excerpts={"inputs/market_facts.json": '{"ticker":"SPY"}'})

    assert "task_id: 01_market_analyst" in task_markdown
    assert "role: market_analyst" in task_markdown
    assert "output_path: outputs/01_market_analyst.attempt0.json" in task_markdown
    assert "inputs/market_facts.json" in task_markdown
    assert "Return exactly one JSON object" in task_markdown
    assert "No markdown fences" in task_markdown
    assert "AnalystOutput" in task_markdown
    assert "Korean" in task_markdown
    assert "# JSON schema" in task_markdown
    assert '"properties"' in task_markdown
    assert '"report_markdown"' in task_markdown


def test_phase_c_prompt_templates_are_present():
    prompt_dir = Path("src/stock_agents/prompts")
    required = {
        "base_system.md.j2",
        "analyst_market.md.j2",
        "analyst_sentiment.md.j2",
        "analyst_news.md.j2",
        "analyst_fundamentals.md.j2",
        "researcher_bull.md.j2",
        "researcher_bear.md.j2",
        "manager_research.md.j2",
        "trader.md.j2",
        "risk_aggressive.md.j2",
        "risk_neutral.md.j2",
        "risk_conservative.md.j2",
        "portfolio_manager.md.j2",
    }

    assert required <= {path.name for path in prompt_dir.glob("*.md.j2")}
