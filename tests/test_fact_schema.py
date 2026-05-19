from datetime import datetime

from stock_agents.schemas.facts import FundamentalsFacts, MarketFacts, OhlcvBar


def test_market_facts_accepts_minimal_ohlcv_payload():
    facts = MarketFacts(
        ticker="SPY",
        trade_date="2026-01-15",
        asset_type="stock",
        ohlcv=[
            OhlcvBar(date="2026-01-15", open=100, high=105, low=99, close=104, volume=123456)
        ],
        fetched_at=datetime(2026, 1, 15, 22, 0, 0),
    )

    assert facts.ticker == "SPY"
    assert facts.trade_date.isoformat() == "2026-01-15"
    assert facts.ohlcv[0].close == 104
    assert facts.warnings == []


def test_crypto_fundamentals_can_record_unavailable_reason_without_company_data():
    facts = FundamentalsFacts(
        ticker="BTC-USD",
        trade_date="2026-01-15",
        asset_type="crypto",
        unavailable_reason="Company fundamentals are not available for crypto asset mode.",
    )

    assert facts.asset_type == "crypto"
    assert facts.company_profile == {}
    assert "not available" in facts.unavailable_reason
