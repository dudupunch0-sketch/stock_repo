from __future__ import annotations

from stock_agents.schemas.outputs import PortfolioDecisionOutput

_KOREAN_DISCLAIMER = "이 리포트는 리서치 보조 자료이며 투자 조언이 아닙니다. 데이터와 판단을 독립적으로 검증하고 필요하면 자격 있는 전문가와 상담하세요."
_ENGLISH_DISCLAIMER = "This report is research assistance, not financial advice. Verify data independently and consult a qualified professional if needed."


def render_final_report(decision: PortfolioDecisionOutput, *, language: str = "Korean") -> str:
    disclaimer = _KOREAN_DISCLAIMER if language.lower().startswith("korean") else _ENGLISH_DISCLAIMER
    evidence_lines = [
        f"- {item.source_type}: {item.quote} (confidence {item.confidence:.2f})"
        for item in decision.supporting_evidence
    ]
    risks = [f"- {risk}" for risk in decision.major_risks]
    heading = f"# {decision.ticker} 분석 리포트" if language.lower().startswith("korean") else f"# {decision.ticker} Analysis Report"
    return "\n".join(
        [
            heading,
            "",
            f"- Date: {decision.trade_date.isoformat()}",
            f"- Rating: {decision.rating.value}",
            f"- Action: {decision.action.value}",
            f"- Confidence: {decision.confidence:.2f}",
            "",
            "## Executive Summary",
            decision.executive_summary,
            "",
            "## Investment Thesis",
            decision.investment_thesis,
            "",
            "## Major Risks",
            *(risks or ["- No major risks were supplied."]),
            "",
            "## Supporting Evidence",
            *(evidence_lines or ["- No supporting evidence was supplied."]),
            "",
            "## Role Detail",
            decision.report_markdown,
            "",
            "## Disclaimer",
            disclaimer,
            "",
        ]
    )
