from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass

from stock_agents.domain.enums import Role
from stock_agents.schemas.outputs import (
    AnalystOutput,
    DebateArgumentOutput,
    PortfolioDecisionOutput,
    ResearchPlanOutput,
    RiskArgumentOutput,
    TraderProposalOutput,
)
from stock_agents.schemas.tasks import AgentTask


@dataclass(frozen=True)
class RoleTaskSpec:
    task_id: str
    output_schema_name: str
    input_paths: tuple[str, ...]
    dependency_output_paths: tuple[str, ...]
    objective: str
    role_description: str


ROLE_TASK_SPECS: dict[Role, RoleTaskSpec] = {
    Role.MARKET_ANALYST: RoleTaskSpec(
        task_id="01_market_analyst",
        output_schema_name="AnalystOutput",
        input_paths=("inputs/market_facts.json", "inputs/technical_facts.json"),
        dependency_output_paths=(),
        objective="Analyze price action and technical market facts with evidence-grounded market signals.",
        role_description="You are the Market Analyst. Analyze price action and technical market facts.",
    ),
    Role.SENTIMENT_ANALYST: RoleTaskSpec(
        task_id="02_sentiment_analyst",
        output_schema_name="AnalystOutput",
        input_paths=("inputs/sentiment_facts.json",),
        dependency_output_paths=(),
        objective="Analyze provided social and sentiment facts without adding unsupported outside claims.",
        role_description="You are the Sentiment Analyst. Analyze provided social and sentiment facts.",
    ),
    Role.NEWS_ANALYST: RoleTaskSpec(
        task_id="02_news_analyst",
        output_schema_name="AnalystOutput",
        input_paths=("inputs/news_facts.json",),
        dependency_output_paths=(),
        objective="Analyze provided ticker and global news facts for material catalysts and risks.",
        role_description="You are the News Analyst. Analyze provided ticker and global news facts.",
    ),
    Role.FUNDAMENTALS_ANALYST: RoleTaskSpec(
        task_id="02_fundamentals_analyst",
        output_schema_name="AnalystOutput",
        input_paths=("inputs/fundamentals_facts.json",),
        dependency_output_paths=(),
        objective="Analyze company fundamentals when available, and clearly report unavailable crypto fundamentals.",
        role_description="You are the Fundamentals Analyst. Analyze provided company fundamentals facts.",
    ),
    Role.BULL_RESEARCHER: RoleTaskSpec(
        task_id="03_bull_researcher",
        output_schema_name="DebateArgumentOutput",
        input_paths=(),
        dependency_output_paths=("outputs/01_market_analyst.latest.json", "outputs/02_news_analyst.latest.json"),
        objective="Build the strongest bullish research argument from validated analyst outputs.",
        role_description="You are the Bull Researcher. Argue the bullish case using only validated prior outputs.",
    ),
    Role.BEAR_RESEARCHER: RoleTaskSpec(
        task_id="04_bear_researcher",
        output_schema_name="DebateArgumentOutput",
        input_paths=(),
        dependency_output_paths=("outputs/01_market_analyst.latest.json", "outputs/02_news_analyst.latest.json"),
        objective="Build the strongest bearish research argument from validated analyst outputs.",
        role_description="You are the Bear Researcher. Argue the bearish case using only validated prior outputs.",
    ),
    Role.RESEARCH_MANAGER: RoleTaskSpec(
        task_id="05_research_manager",
        output_schema_name="ResearchPlanOutput",
        input_paths=(),
        dependency_output_paths=("outputs/03_bull_researcher.latest.json", "outputs/04_bear_researcher.latest.json"),
        objective="Resolve the research debate into a balanced recommendation and rationale.",
        role_description="You are the Research Manager. Synthesize bull and bear arguments into a balanced research plan.",
    ),
    Role.TRADER: RoleTaskSpec(
        task_id="06_trader",
        output_schema_name="TraderProposalOutput",
        input_paths=(),
        dependency_output_paths=("outputs/05_research_manager.latest.json",),
        objective="Translate the research manager recommendation into a cautious trade proposal.",
        role_description="You are the Trader. Convert the research plan into a proposal without guaranteeing returns.",
    ),
    Role.RISK_AGGRESSIVE: RoleTaskSpec(
        task_id="07_risk_aggressive",
        output_schema_name="RiskArgumentOutput",
        input_paths=(),
        dependency_output_paths=("outputs/06_trader.latest.json",),
        objective="Assess the trader proposal from an aggressive risk posture.",
        role_description="You are the Aggressive Risk Analyst. Identify upside-biased risk adjustments.",
    ),
    Role.RISK_CONSERVATIVE: RoleTaskSpec(
        task_id="08_risk_conservative",
        output_schema_name="RiskArgumentOutput",
        input_paths=(),
        dependency_output_paths=("outputs/06_trader.latest.json",),
        objective="Assess the trader proposal from a conservative risk posture.",
        role_description="You are the Conservative Risk Analyst. Identify capital-preservation risk adjustments.",
    ),
    Role.RISK_NEUTRAL: RoleTaskSpec(
        task_id="09_risk_neutral",
        output_schema_name="RiskArgumentOutput",
        input_paths=(),
        dependency_output_paths=("outputs/06_trader.latest.json",),
        objective="Assess the trader proposal from a neutral risk posture.",
        role_description="You are the Neutral Risk Analyst. Balance upside and downside risk adjustments.",
    ),
    Role.PORTFOLIO_MANAGER: RoleTaskSpec(
        task_id="10_portfolio_manager",
        output_schema_name="PortfolioDecisionOutput",
        input_paths=(),
        dependency_output_paths=(
            "outputs/05_research_manager.latest.json",
            "outputs/06_trader.latest.json",
            "outputs/07_risk_aggressive.latest.json",
            "outputs/08_risk_conservative.latest.json",
            "outputs/09_risk_neutral.latest.json",
        ),
        objective="Produce the final research decision with a non-financial-advice disclaimer flag.",
        role_description="You are the Portfolio Manager. Synthesize validated prior outputs into a final research decision.",
    ),
}

_COMMON_EVIDENCE_RULES = (
    "Every material claim should cite provided fact files or dependency outputs.",
    "Use agent_reasoning only for synthesis that is clearly derived from provided evidence.",
)
_COMMON_FORBIDDEN_CLAIMS = (
    "Do not guarantee future returns.",
    "Do not present research assistance as financial advice.",
    "Do not add outside facts that are absent from the input package.",
)

_OUTPUT_SCHEMA_MODELS = {
    "AnalystOutput": AnalystOutput,
    "DebateArgumentOutput": DebateArgumentOutput,
    "ResearchPlanOutput": ResearchPlanOutput,
    "TraderProposalOutput": TraderProposalOutput,
    "RiskArgumentOutput": RiskArgumentOutput,
    "PortfolioDecisionOutput": PortfolioDecisionOutput,
}


def build_agent_task(*, role: Role, ticker: str, trade_date: str, language: str = "Korean") -> AgentTask:
    spec = ROLE_TASK_SPECS[Role(role)]
    return AgentTask(
        task_id=spec.task_id,
        role=Role(role),
        ticker=ticker,
        trade_date=trade_date,
        language=language,
        input_paths=list(spec.input_paths),
        dependency_output_paths=list(spec.dependency_output_paths),
        output_schema_name=spec.output_schema_name,
        output_path=f"outputs/{spec.task_id}.attempt0.json",
        objective=spec.objective,
        evidence_rules=list(_COMMON_EVIDENCE_RULES),
        forbidden_claims=list(_COMMON_FORBIDDEN_CLAIMS),
    )


def render_task(task: AgentTask, *, input_excerpts: Mapping[str, str] | None = None) -> str:
    excerpts = input_excerpts or {}
    spec = ROLE_TASK_SPECS.get(task.role)
    lines: list[str] = [
        "---",
        f"task_id: {task.task_id}",
        f"role: {task.role.value}",
        f"ticker: {task.ticker}",
        f"trade_date: {task.trade_date.isoformat()}",
        f"language: {task.language}",
        f"output_schema: {task.output_schema_name}",
        f"output_path: {task.output_path}",
        "input_paths:",
    ]
    if task.input_paths:
        lines.extend(f"  - {path}" for path in task.input_paths)
    else:
        lines.append("  []")
    lines.append("dependency_output_paths:")
    if task.dependency_output_paths:
        lines.extend(f"  - {path}" for path in task.dependency_output_paths)
    else:
        lines.append("  []")
    lines.extend(
        [
            f"max_repair_attempts: {task.max_repair_attempts}",
            "---",
            "",
            "# Role",
            spec.role_description if spec else f"You are the {task.role.value} role.",
            "",
            "# Objective",
            task.objective,
            "",
            "# Input files",
        ]
    )
    if task.input_paths:
        lines.extend(f"- {path}" for path in task.input_paths)
    else:
        lines.append("- none; use dependency outputs only")
    lines.extend(["", "# Dependency outputs"])
    if task.dependency_output_paths:
        lines.extend(f"- {path}" for path in task.dependency_output_paths)
    else:
        lines.append("- none")

    if excerpts:
        lines.extend(["", "# Input excerpts"])
        for path, excerpt in excerpts.items():
            lines.extend([f"## {path}", "```json", excerpt, "```"])

    lines.extend(["", "# Evidence rules"])
    lines.extend(f"- {rule}" for rule in task.evidence_rules)
    lines.extend(["", "# Forbidden claims"])
    lines.extend(f"- {claim}" for claim in task.forbidden_claims)
    lines.extend(
        [
            "",
            "# Required output",
            f"Return exactly one JSON object matching this schema: {task.output_schema_name}.",
            "No markdown fences. No prose before or after the JSON object.",
            f"Write human-readable fields in {task.language}.",
            "Do not add facts that are not supported by input files or dependency outputs.",
        ]
    )
    schema_model = _OUTPUT_SCHEMA_MODELS.get(task.output_schema_name)
    if schema_model is not None:
        schema_json = json.dumps(schema_model.model_json_schema(), ensure_ascii=False, indent=2)
        lines.extend(["", "# JSON schema", "```json", schema_json, "```"])
    return "\n".join(lines) + "\n"
