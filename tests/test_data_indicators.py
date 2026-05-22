from datetime import date, timedelta

from stock_agents.data.indicators import compute_rsi, compute_sma, latest_indicator_summary
from stock_agents.schemas.facts import OhlcvBar


def _bars(closes):
    return [
        OhlcvBar(date=date(2026, 1, 1) + timedelta(days=index), open=value, high=value + 1, low=value - 1, close=value, volume=1000)
        for index, value in enumerate(closes)
    ]


def test_compute_sma_returns_none_until_window_is_full():
    values = compute_sma([10, 20, 30, 40], window=3)

    assert values == [None, None, 20.0, 30.0]


def test_compute_rsi_returns_neutral_for_flat_prices_after_window():
    values = compute_rsi([10, 10, 10, 10, 10], window=3)

    assert values[:3] == [None, None, None]
    assert values[-1] == 50.0


def test_latest_indicator_summary_builds_schema_ready_points():
    closes = list(range(1, 221))
    facts = latest_indicator_summary(ticker="SPY", trade_date="2026-08-08", bars=_bars(closes))

    assert facts.ticker == "SPY"
    assert facts.trade_date.isoformat() == "2026-08-08"
    assert facts.selected_indicators == ["sma_3", "sma_5", "sma_20", "sma_50", "sma_200", "rsi_3", "rsi_14"]
    assert facts.indicators["sma_3"][-1].value == 219.0
    assert facts.indicators["sma_5"][-1].value == 218.0
    assert facts.indicators["sma_20"][-1].value == 210.5
    assert facts.indicators["sma_50"][-1].value == 195.5
    assert facts.indicators["sma_200"][-1].value == 120.5
    assert facts.indicators["rsi_3"][-1].value == 100.0
    assert facts.indicators["rsi_14"][-1].value == 100.0
