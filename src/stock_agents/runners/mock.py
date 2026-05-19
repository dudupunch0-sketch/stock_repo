from __future__ import annotations

import json
import re
import time
from pathlib import Path

from stock_agents.domain.enums import Direction, Rating, Role, TraderAction
from stock_agents.runners.base import RunnerResult


_METADATA_RE = re.compile(r"^(task_id|role|ticker|trade_date|language|output_schema):\s*(.+)$", re.MULTILINE)


class MockRunner:
    name = "mock"

    def run(self, prompt: str, *, cwd: Path, timeout_seconds: int) -> RunnerResult:
        started = time.monotonic()
        metadata = {key: value.strip() for key, value in _METADATA_RE.findall(prompt)}
        role = Role(metadata.get("role", Role.MARKET_ANALYST.value))
        ticker = metadata.get("ticker", "UNKNOWN")
        trade_date = metadata.get("trade_date", "1970-01-01")
        payload = _payload_for_role(role, ticker=ticker, trade_date=trade_date)
        return RunnerResult(
            runner=self.name,
            command=["mock-runner"],
            exit_code=0,
            stdout=json.dumps(payload, ensure_ascii=False, sort_keys=True),
            stderr="",
            duration_seconds=time.monotonic() - started,
            timed_out=False,
        )


def _evidence() -> dict[str, object]:
    return {
        "source_type": "market_facts",
        "source_path": "inputs/market_facts.json",
        "quote": "Deterministic mock evidence from supplied market facts.",
        "confidence": 0.6,
    }


def _payload_for_role(role: Role, *, ticker: str, trade_date: str) -> dict[str, object]:
    if role is Role.PORTFOLIO_MANAGER:
        return {
            "role": role.value,
            "ticker": ticker,
            "trade_date": trade_date,
            "rating": Rating.HOLD.value,
            "action": TraderAction.HOLD.value,
            "executive_summary": "모의 실행 결과, 관망 의견입니다.",
            "investment_thesis": "입력 fact package만으로는 강한 방향성을 확정하지 않습니다.",
            "major_risks": ["MockRunner output is not live market research."],
            "supporting_evidence": [_evidence()],
            "confidence": 0.5,
            "not_financial_advice": True,
            "report_markdown": "## 모의 포트폴리오 결정\n\n투자 조언이 아닌 테스트용 리서치 보조 결과입니다.",
        }

    if role in {Role.BULL_RESEARCHER, Role.BEAR_RESEARCHER}:
        stance = "bull" if role is Role.BULL_RESEARCHER else "bear"
        return {
            "role": role.value,
            "ticker": ticker,
            "trade_date": trade_date,
            "stance": stance,
            "argument": "Mock debate argument based on deterministic fixtures.",
            "strongest_points": [_signal()],
            "rebuttals": [],
            "risks_or_upside": [],
            "confidence": 0.5,
            "report_markdown": "## Mock debate argument",
        }

    if role is Role.RESEARCH_MANAGER:
        return {
            "role": role.value,
            "ticker": ticker,
            "trade_date": trade_date,
            "recommendation": Rating.HOLD.value,
            "rationale": "Mock research manager keeps the recommendation neutral.",
            "strategic_actions": "Wait for validated real-run evidence.",
            "supporting_evidence": [_evidence()],
            "disputed_points": [],
            "confidence": 0.5,
            "report_markdown": "## Mock research plan",
        }

    if role is Role.TRADER:
        return {
            "role": role.value,
            "ticker": ticker,
            "trade_date": trade_date,
            "action": TraderAction.HOLD.value,
            "reasoning": "Mock trader avoids action without real evidence.",
            "confidence": 0.5,
            "supporting_evidence": [_evidence()],
            "report_markdown": "## Mock trader proposal",
        }

    if role in {Role.RISK_AGGRESSIVE, Role.RISK_CONSERVATIVE, Role.RISK_NEUTRAL}:
        posture = role.value.replace("risk_", "")
        return {
            "role": role.value,
            "ticker": ticker,
            "trade_date": trade_date,
            "risk_posture": posture,
            "argument": "Mock risk argument.",
            "recommended_adjustments": ["Use real validated data before acting."],
            "major_risks": ["Mock output risk."],
            "confidence": 0.5,
            "report_markdown": "## Mock risk argument",
        }

    return {
        "role": role.value,
        "ticker": ticker,
        "trade_date": trade_date,
        "summary": "모의 분석은 중립 신호를 반환합니다.",
        "overall_direction": Direction.NEUTRAL.value,
        "confidence": 0.5,
        "signals": [_signal()],
        "risks": ["MockRunner output is deterministic test data."],
        "unknowns": ["Real market data has not been collected in this runner."],
        "agent_only_findings": [],
        "coverage_gaps": [],
        "report_markdown": "## 모의 분석\n\nMockRunner가 생성한 테스트용 결과입니다.",
    }


def _signal() -> dict[str, object]:
    return {
        "name": "mock_neutral_signal",
        "direction": Direction.NEUTRAL.value,
        "confidence": 0.5,
        "evidence": [_evidence()],
    }
