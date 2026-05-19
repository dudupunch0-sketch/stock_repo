from __future__ import annotations

import json

from stock_agents.schemas.outputs import (
    AnalystOutput,
    DebateArgumentOutput,
    PortfolioDecisionOutput,
    ResearchPlanOutput,
    RiskArgumentOutput,
    TraderProposalOutput,
)
from stock_agents.schemas.tasks import AgentTask

_OUTPUT_SCHEMA_MODELS = {
    "AnalystOutput": AnalystOutput,
    "DebateArgumentOutput": DebateArgumentOutput,
    "ResearchPlanOutput": ResearchPlanOutput,
    "TraderProposalOutput": TraderProposalOutput,
    "RiskArgumentOutput": RiskArgumentOutput,
    "PortfolioDecisionOutput": PortfolioDecisionOutput,
}


def build_repair_task(
    *,
    task: AgentTask,
    original_task_text: str,
    raw_output: str,
    validation_error: str,
    attempt_number: int,
) -> str:
    schema_model = _OUTPUT_SCHEMA_MODELS.get(task.output_schema_name)
    schema_text = "{}"
    if schema_model is not None:
        schema_text = json.dumps(schema_model.model_json_schema(), ensure_ascii=False, indent=2)

    lines = [
        f"# Repair attempt {attempt_number} for {task.task_id}",
        "",
        "The previous runner output could not be validated. Return a corrected output for the same task.",
        "",
        "## Metadata",
        f"- task_id: {task.task_id}",
        f"- role: {task.role.value}",
        f"- ticker: {task.ticker}",
        f"- trade_date: {task.trade_date.isoformat()}",
        f"- language: {task.language}",
        f"- output_schema: {task.output_schema_name}",
        "",
        "## Repair rules",
        "- Return exactly one corrected JSON object. No markdown fences. No prose before or after JSON.",
        "- Do not add new facts, prices, dates, sources, or claims that were absent from the original task.",
        "- Only correct structure, missing required fields, enum values, and type/format issues.",
        "- Keep human-readable fields in the requested language.",
        "- Preserve the intended role, ticker, and trade_date.",
        "",
        "## Validation error",
        "~~~text",
        validation_error.strip(),
        "~~~",
        "",
        "## Previous raw output",
        "~~~text",
        raw_output.strip(),
        "~~~",
        "",
        "## Original task",
        "~~~markdown",
        original_task_text.strip(),
        "~~~",
        "",
        "## Required JSON schema",
        "~~~json",
        schema_text,
        "~~~",
        "",
        "Return exactly one corrected JSON object now.",
    ]
    return "\n".join(lines) + "\n"
