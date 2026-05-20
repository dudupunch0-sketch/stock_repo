import pytest
from pydantic import ValidationError

from stock_agents.domain.enums import Direction, Role
from stock_agents.orchestration.validator import extract_json_object, validate_output_for_role
from stock_agents.schemas.outputs import AnalystOutput, Evidence, PortfolioDecisionOutput, Signal


def _evidence():
    return Evidence(
        source_type="market_facts",
        source_path="inputs/market_facts.json",
        quote="Close finished above the short moving average.",
        confidence=0.8,
    )


def test_analyst_output_rejects_confidence_outside_zero_to_one():
    with pytest.raises(ValidationError):
        AnalystOutput(
            role=Role.MARKET_ANALYST,
            ticker="SPY",
            trade_date="2026-01-15",
            summary="summary",
            overall_direction=Direction.BULLISH,
            confidence=1.5,
            signals=[Signal(name="trend", direction=Direction.BULLISH, confidence=0.7, evidence=[_evidence()])],
            risks=[],
            unknowns=[],
            report_markdown="report",
        )


def test_portfolio_decision_requires_true_non_financial_advice_flag():
    payload = {
        "role": "portfolio_manager",
        "ticker": "SPY",
        "trade_date": "2026-01-15",
        "rating": "Hold",
        "action": "Hold",
        "executive_summary": "요약",
        "investment_thesis": "논지",
        "major_risks": ["risk"],
        "supporting_evidence": [_evidence().model_dump()],
        "confidence": 0.6,
        "not_financial_advice": False,
        "report_markdown": "report",
    }

    with pytest.raises(ValidationError):
        PortfolioDecisionOutput(**payload)


def test_extract_json_object_handles_fenced_json_and_validate_for_role():
    raw = """Here is the output:\n```json\n{\"role\": \"market_analyst\", \"ticker\": \"SPY\", \"trade_date\": \"2026-01-15\", \"summary\": \"ok\", \"overall_direction\": \"neutral\", \"confidence\": 0.5, \"signals\": [], \"risks\": [], \"unknowns\": [], \"report_markdown\": \"ok\"}\n```"""

    payload = extract_json_object(raw)
    output = validate_output_for_role(Role.MARKET_ANALYST, payload)

    assert output.role == Role.MARKET_ANALYST
    assert output.ticker == "SPY"


def test_extract_json_object_prefers_first_balanced_object_before_later_fence():
    raw = 'prefix {"selected": "first"} later ```json\n{"selected": "fenced"}\n```'

    payload = extract_json_object(raw)

    assert payload == {"selected": "first"}
