from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from stock_agents.domain.enums import Direction, Rating, Role, TraderAction


class Evidence(BaseModel):
    source_type: Literal[
        "market_facts",
        "technical_facts",
        "fundamentals_facts",
        "news_facts",
        "sentiment_facts",
        "prior_context",
        "agent_reasoning",
    ]
    source_path: str | None = None
    quote: str
    date: str | None = None
    url: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class Signal(BaseModel):
    name: str
    direction: Direction
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[Evidence] = Field(default_factory=list)


class AnalystOutput(BaseModel):
    role: Role
    ticker: str
    trade_date: date
    summary: str
    overall_direction: Direction
    confidence: float = Field(ge=0.0, le=1.0)
    signals: list[Signal]
    risks: list[str]
    unknowns: list[str]
    agent_only_findings: list[str] = Field(default_factory=list)
    coverage_gaps: list[str] = Field(default_factory=list)
    report_markdown: str


class DebateArgumentOutput(BaseModel):
    role: Literal[Role.BULL_RESEARCHER, Role.BEAR_RESEARCHER]
    ticker: str
    trade_date: date
    stance: Literal["bull", "bear"]
    argument: str
    strongest_points: list[Signal]
    rebuttals: list[str]
    risks_or_upside: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    report_markdown: str


class ResearchPlanOutput(BaseModel):
    role: Literal[Role.RESEARCH_MANAGER]
    ticker: str
    trade_date: date
    recommendation: Rating
    rationale: str
    strategic_actions: str
    supporting_evidence: list[Evidence]
    disputed_points: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    report_markdown: str


class TraderProposalOutput(BaseModel):
    role: Literal[Role.TRADER]
    ticker: str
    trade_date: date
    action: TraderAction
    reasoning: str
    entry_price: float | None = None
    stop_loss: float | None = None
    position_sizing: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_evidence: list[Evidence]
    report_markdown: str


class RiskArgumentOutput(BaseModel):
    role: Literal[Role.RISK_AGGRESSIVE, Role.RISK_CONSERVATIVE, Role.RISK_NEUTRAL]
    ticker: str
    trade_date: date
    risk_posture: Literal["aggressive", "conservative", "neutral"]
    argument: str
    recommended_adjustments: list[str]
    major_risks: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    report_markdown: str


class PortfolioDecisionOutput(BaseModel):
    role: Literal[Role.PORTFOLIO_MANAGER]
    ticker: str
    trade_date: date
    rating: Rating
    action: TraderAction
    executive_summary: str
    investment_thesis: str
    price_target: float | None = None
    time_horizon: str | None = None
    position_sizing: str | None = None
    major_risks: list[str]
    supporting_evidence: list[Evidence]
    confidence: float = Field(ge=0.0, le=1.0)
    not_financial_advice: bool = True
    report_markdown: str

    @field_validator("not_financial_advice")
    @classmethod
    def require_disclaimer_flag(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("portfolio decisions must set not_financial_advice=true")
        return value
