from datetime import date

from stock_agents.data.indicators import compute_rsi, compute_sma, latest_indicator_summary
from stock_agents.schemas.facts import OhlcvBar


def _bars(closes):
    return [
        OhlcvBar(date=date(2026, 1, index + 1), open=value, high=value + 1, low=value - 1, close=value, volume=1000)
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
    facts = latest_indicator_summary(ticker="SPY", trade_date="2026-01-05", bars=_bars([10, 11, 12, 13, 14]))

    assert facts.ticker == "SPY"
    assert facts.trade_date.isoformat() == "2026-01-05"
    assert facts.selected_indicators == ["sma_3", "sma_5", "rsi_3"]
    assert facts.indicators["sma_3"][-1].value == 13.0
    assert facts.indicators["sma_5"][-1].value == 12.0
    assert facts.indicators["rsi_3"][-1].value == 100.0
