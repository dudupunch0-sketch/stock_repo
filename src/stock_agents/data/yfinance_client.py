from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone

from stock_agents.schemas.facts import MarketFacts, OhlcvBar

YFINANCE_LOOKBACK_DAYS = 370
OFFLINE_FIXTURE_BARS = 252


def infer_asset_type(ticker: str) -> str:
    upper = ticker.upper()
    if upper.endswith("-USD") or upper.endswith("-USDT") or upper in {"BTC", "ETH", "SOL"}:
        return "crypto"
    return "stock"


def fetch_market_facts(
    *,
    ticker: str,
    trade_date: str | date,
    asset_type: str | None = None,
    benchmark_ticker: str | None = None,
) -> MarketFacts:
    """Fetch or synthesize minimal OHLCV facts.

    yfinance is the preferred path and fetches at least one calendar year of
    daily history. If it is disabled, not installed, or not usable, this returns
    one trading year of deterministic offline bars so the rest of the
    file-handoff pipeline remains locally testable.
    """
    parsed_date = date.fromisoformat(trade_date) if isinstance(trade_date, str) else trade_date
    selected_asset_type = asset_type or infer_asset_type(ticker)
    warnings: list[str] = []
    bars = _try_yfinance(ticker=ticker, trade_date=parsed_date, warnings=warnings)
    data_source = "yfinance"
    if not bars:
        bars = _offline_bars(ticker=ticker, trade_date=parsed_date)
        data_source = "offline_fixture"
        warnings.append("yfinance data unavailable; used deterministic offline fixture bars.")
    return MarketFacts(
        ticker=ticker,
        trade_date=parsed_date,
        asset_type=selected_asset_type,  # type: ignore[arg-type]
        currency="USD",
        ohlcv=bars,
        benchmark_ticker=benchmark_ticker,
        data_source=data_source,
        fetched_at=datetime.now(timezone.utc),
        warnings=warnings,
    )


def _try_yfinance(*, ticker: str, trade_date: date, warnings: list[str]) -> list[OhlcvBar]:
    if os.environ.get("STOCK_AGENTS_DISABLE_YFINANCE") == "1":
        warnings.append("yfinance disabled via STOCK_AGENTS_DISABLE_YFINANCE.")
        return []

    try:
        import yfinance as yf  # type: ignore[import-not-found]
    except Exception:
        return []

    start = trade_date - timedelta(days=YFINANCE_LOOKBACK_DAYS)
    end = trade_date + timedelta(days=1)
    try:
        frame = yf.Ticker(ticker).history(start=start.isoformat(), end=end.isoformat(), auto_adjust=False)
    except Exception as exc:  # pragma: no cover - depends on network/yfinance runtime.
        warnings.append(f"yfinance history failed: {exc}")
        return []
    if frame is None or getattr(frame, "empty", True):
        return []

    bars: list[OhlcvBar] = []
    for index, row in frame.iterrows():  # pragma: no cover - pandas/yfinance not installed in local test env.
        bar_date = index.date() if hasattr(index, "date") else date.fromisoformat(str(index)[:10])
        bars.append(
            OhlcvBar(
                date=bar_date,
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=int(row.get("Volume", 0) or 0),
            )
        )
    return bars


def _offline_bars(*, ticker: str, trade_date: date) -> list[OhlcvBar]:
    seed = sum(ord(ch) for ch in ticker.upper()) % 37
    base = 90.0 + seed
    bars: list[OhlcvBar] = []
    for step, current_date in enumerate(_trading_dates_through(trade_date, count=OFFLINE_FIXTURE_BARS)):
        close = round(base + step * 0.8 + ((step % 3) - 1) * 0.35, 2)
        open_price = round(close - 0.4, 2)
        high = round(max(open_price, close) + 1.1, 2)
        low = round(min(open_price, close) - 1.0, 2)
        bars.append(OhlcvBar(date=current_date, open=open_price, high=high, low=low, close=close, volume=1_000_000 + step * 1000))
    return bars


def _trading_dates_through(trade_date: date, *, count: int) -> list[date]:
    dates: list[date] = []
    current = trade_date
    while len(dates) < count:
        if current.weekday() < 5:
            dates.append(current)
        current -= timedelta(days=1)
    return list(reversed(dates))
