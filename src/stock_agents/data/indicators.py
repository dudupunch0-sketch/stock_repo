from __future__ import annotations

from datetime import date
from typing import Iterable

from stock_agents.schemas.facts import IndicatorPoint, OhlcvBar, TechnicalFacts


def compute_sma(values: Iterable[float], *, window: int) -> list[float | None]:
    if window <= 0:
        raise ValueError("window must be positive")
    series = [float(value) for value in values]
    output: list[float | None] = []
    for index in range(len(series)):
        if index + 1 < window:
            output.append(None)
            continue
        chunk = series[index + 1 - window : index + 1]
        output.append(round(sum(chunk) / window, 6))
    return output


def compute_rsi(values: Iterable[float], *, window: int = 14) -> list[float | None]:
    if window <= 0:
        raise ValueError("window must be positive")
    series = [float(value) for value in values]
    output: list[float | None] = []
    for index in range(len(series)):
        if index < window:
            output.append(None)
            continue
        gains = 0.0
        losses = 0.0
        for previous, current in zip(series[index - window : index], series[index - window + 1 : index + 1], strict=True):
            delta = current - previous
            if delta >= 0:
                gains += delta
            else:
                losses += -delta
        if gains == 0 and losses == 0:
            output.append(50.0)
        elif losses == 0:
            output.append(100.0)
        else:
            relative_strength = gains / losses
            output.append(round(100 - (100 / (1 + relative_strength)), 6))
    return output


def latest_indicator_summary(*, ticker: str, trade_date: str | date, bars: list[OhlcvBar]) -> TechnicalFacts:
    closes = [bar.close for bar in bars]
    indicator_values = {
        "sma_3": compute_sma(closes, window=3),
        "sma_5": compute_sma(closes, window=5),
        "sma_20": compute_sma(closes, window=20),
        "sma_50": compute_sma(closes, window=50),
        "sma_200": compute_sma(closes, window=200),
        "rsi_3": compute_rsi(closes, window=3),
        "rsi_14": compute_rsi(closes, window=14),
    }
    indicators = {
        name: [IndicatorPoint(date=bar.date, value=value) for bar, value in zip(bars, values, strict=True)]
        for name, values in indicator_values.items()
    }
    warnings: list[str] = []
    if len(bars) < 200:
        warnings.append("Fewer than 200 OHLCV bars were available; long-horizon indicators may be null.")
    return TechnicalFacts(
        ticker=ticker,
        trade_date=trade_date,
        indicators=indicators,
        selected_indicators=list(indicator_values),
        warnings=warnings,
    )
