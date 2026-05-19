from stock_agents.domain.enums import Rating, Role, TraderAction
from stock_agents.reporting.renderer import render_final_report
from stock_agents.schemas.outputs import Evidence, PortfolioDecisionOutput


def test_render_final_report_includes_korean_disclaimer_and_decision():
    decision = PortfolioDecisionOutput(
        role=Role.PORTFOLIO_MANAGER,
        ticker="SPY",
        trade_date="2026-01-15",
        rating=Rating.HOLD,
        action=TraderAction.HOLD,
        executive_summary="모의 포트폴리오 요약입니다.",
        investment_thesis="검증된 입력만 기반으로 관망합니다.",
        major_risks=["데이터가 모의 fixture입니다."],
        supporting_evidence=[
            Evidence(
                source_type="market_facts",
                source_path="inputs/market_facts.json",
                quote="offline fixture",
                confidence=0.5,
            )
        ],
        confidence=0.5,
        not_financial_advice=True,
        report_markdown="## 세부 판단\n\n관망입니다.",
    )

    report = render_final_report(decision, language="Korean")

    assert "# SPY 분석 리포트" in report
    assert "Hold" in report
    assert "모의 포트폴리오 요약입니다." in report
    assert "투자 조언이 아닙니다" in report
    assert "offline fixture" in report
