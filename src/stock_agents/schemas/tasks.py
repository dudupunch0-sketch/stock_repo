from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from stock_agents.domain.enums import Role


class AgentTask(BaseModel):
    task_id: str
    role: Role
    ticker: str
    trade_date: date
    language: str
    input_paths: list[str]
    dependency_output_paths: list[str] = Field(default_factory=list)
    output_schema_name: str
    output_path: str
    objective: str
    evidence_rules: list[str]
    forbidden_claims: list[str]
    max_repair_attempts: int = 1
