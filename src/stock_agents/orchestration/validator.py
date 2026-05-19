from __future__ import annotations

import json
import re
from typing import Any

from stock_agents.domain.enums import Role
from stock_agents.schemas.outputs import (
    AnalystOutput,
    DebateArgumentOutput,
    PortfolioDecisionOutput,
    ResearchPlanOutput,
    RiskArgumentOutput,
    TraderProposalOutput,
)

_ANALYST_ROLES = {
    Role.MARKET_ANALYST,
    Role.SENTIMENT_ANALYST,
    Role.NEWS_ANALYST,
    Role.FUNDAMENTALS_ANALYST,
}


_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


def extract_json_object(raw_text: str) -> dict[str, Any]:
    """Extract the first JSON object from CLI runner output."""
    stripped = raw_text.strip()
    candidates: list[str] = []
    if stripped.startswith("{"):
        candidates.append(stripped)
    candidates.extend(match.group(1).strip() for match in _FENCED_JSON_RE.finditer(raw_text))
    balanced = _first_balanced_json_object(raw_text)
    if balanced is not None:
        candidates.append(balanced)

    last_error: Exception | None = None
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc
            continue
        if isinstance(parsed, dict):
            return parsed
        raise ValueError("extracted JSON value is not an object")

    if last_error is not None:
        raise ValueError(f"could not parse JSON object: {last_error}") from last_error
    raise ValueError("could not find JSON object in runner output")


def _first_balanced_json_object(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False
    for index, ch in enumerate(text[start:], start=start):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def validate_output_for_role(role: Role, payload: dict[str, Any]):
    role = Role(role)
    if role in _ANALYST_ROLES:
        output = AnalystOutput(**payload)
    elif role in {Role.BULL_RESEARCHER, Role.BEAR_RESEARCHER}:
        output = DebateArgumentOutput(**payload)
    elif role is Role.RESEARCH_MANAGER:
        output = ResearchPlanOutput(**payload)
    elif role is Role.TRADER:
        output = TraderProposalOutput(**payload)
    elif role in {Role.RISK_AGGRESSIVE, Role.RISK_CONSERVATIVE, Role.RISK_NEUTRAL}:
        output = RiskArgumentOutput(**payload)
    elif role is Role.PORTFOLIO_MANAGER:
        output = PortfolioDecisionOutput(**payload)
    else:  # pragma: no cover - Role enum is exhaustive for now.
        raise ValueError(f"unsupported role: {role.value}")

    if Role(output.role) != role:
        raise ValueError(f"role mismatch: expected {role.value}, got {output.role}")
    return output
