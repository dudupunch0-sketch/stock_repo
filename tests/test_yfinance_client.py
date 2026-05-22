import sys
from datetime import date, datetime, timedelta
from types import SimpleNamespace

from stock_agents.data.yfinance_client import (
    OFFLINE_FIXTURE_BARS,
    YFINANCE_LOOKBACK_DAYS,
    _offline_bars,
    _try_yfinance,
)


def test_yfinance_history_requests_at_least_one_year(monkeypatch):
    captured = {}

    class FakeFrame:
        empty = False

        def iterrows(self):
            return iter([(datetime(2026, 5, 21), {"Open": 1, "High": 2, "Low": 0.5, "Close": 1.5, "Volume": 123})])

    class FakeTicker:
        def __init__(self, ticker):
            captured["ticker"] = ticker

        def history(self, *, start, end, auto_adjust):
            captured.update({"start": start, "end": end, "auto_adjust": auto_adjust})
            return FakeFrame()

    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(Ticker=FakeTicker))

    bars = _try_yfinance(ticker="NVDA", trade_date=date(2026, 5, 22), warnings=[])

    assert captured == {
        "ticker": "NVDA",
        "start": (date(2026, 5, 22) - timedelta(days=YFINANCE_LOOKBACK_DAYS)).isoformat(),
        "end": "2026-05-23",
        "auto_adjust": False,
    }
    assert len(bars) == 1
    assert bars[0].date.isoformat() == "2026-05-21"


def test_offline_fixture_covers_one_trading_year():
    bars = _offline_bars(ticker="SPY", trade_date=date(2026, 1, 18))

    assert len(bars) == OFFLINE_FIXTURE_BARS
    assert all(bar.date.weekday() < 5 for bar in bars)
    assert bars[-1].date.isoformat() == "2026-01-16"
