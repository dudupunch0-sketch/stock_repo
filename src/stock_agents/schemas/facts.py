from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class OhlcvBar(BaseModel):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int = Field(ge=0)


class IndicatorPoint(BaseModel):
    date: date
    value: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class NewsItem(BaseModel):
    title: str
    published_at: datetime | None = None
    source: str | None = None
    url: str | None = None
    summary: str | None = None


class SocialItem(BaseModel):
    text: str
    source: str
    published_at: datetime | None = None
    url: str | None = None
    score: float | None = None


class MarketFacts(BaseModel):
    ticker: str
    trade_date: date
    asset_type: Literal["stock", "crypto"]
    currency: str | None = None
    ohlcv: list[OhlcvBar]
    benchmark_ticker: str | None = None
    data_source: str = "yfinance"
    fetched_at: datetime
    warnings: list[str] = Field(default_factory=list)


class TechnicalFacts(BaseModel):
    ticker: str
    trade_date: date
    indicators: dict[str, list[IndicatorPoint]]
    selected_indicators: list[str]
    warnings: list[str] = Field(default_factory=list)


class FundamentalsFacts(BaseModel):
    ticker: str
    trade_date: date
    asset_type: Literal["stock", "crypto"]
    company_profile: dict[str, Any] = Field(default_factory=dict)
    financial_metrics: dict[str, Any] = Field(default_factory=dict)
    statements: dict[str, Any] = Field(default_factory=dict)
    unavailable_reason: str | None = None
    warnings: list[str] = Field(default_factory=list)


class NewsFacts(BaseModel):
    ticker: str
    trade_date: date
    ticker_news: list[NewsItem]
    global_news: list[NewsItem]
    warnings: list[str] = Field(default_factory=list)


class SentimentFacts(BaseModel):
    ticker: str
    trade_date: date
    stocktwits: list[SocialItem] = Field(default_factory=list)
    reddit: list[SocialItem] = Field(default_factory=list)
    news_sentiment_inputs: list[NewsItem] = Field(default_factory=list)
    unavailable_sources: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
