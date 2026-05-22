from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from stock_agents.schemas.facts import NewsFacts, NewsItem, SentimentFacts

NEWS_LOOKBACK_DAYS = 7
TICKER_NEWS_LIMIT = 20
GLOBAL_NEWS_LIMIT = 10
GLOBAL_NEWS_QUERIES = (
    "Federal Reserve interest rates inflation",
    "S&P 500 earnings GDP economic outlook",
    "geopolitical risk trade war sanctions",
    "ECB Bank of England BOJ central bank policy",
    "oil commodities supply chain energy",
)


def collect_news_facts(*, ticker: str, trade_date: str | date) -> NewsFacts:
    parsed_date = _parse_trade_date(trade_date)
    warnings: list[str] = []
    if os.environ.get("STOCK_AGENTS_DISABLE_NEWS") == "1":
        return NewsFacts(
            ticker=ticker,
            trade_date=parsed_date,
            ticker_news=[],
            global_news=[],
            warnings=["yfinance news disabled via STOCK_AGENTS_DISABLE_NEWS."],
        )

    try:
        import yfinance as yf  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - depends on runtime environment.
        return NewsFacts(
            ticker=ticker,
            trade_date=parsed_date,
            ticker_news=[],
            global_news=[],
            warnings=[f"yfinance news unavailable: {exc}"],
        )

    start_dt = datetime.combine(parsed_date - timedelta(days=NEWS_LOOKBACK_DAYS), time.min)
    end_dt = datetime.combine(parsed_date + timedelta(days=1), time.max)
    ticker_news = _collect_ticker_news(
        yf=yf,
        ticker=ticker,
        start_dt=start_dt,
        end_dt=end_dt,
        warnings=warnings,
    )
    global_news = _collect_global_news(
        yf=yf,
        trade_date=parsed_date,
        warnings=warnings,
    )
    return NewsFacts(
        ticker=ticker,
        trade_date=parsed_date,
        ticker_news=ticker_news,
        global_news=global_news,
        warnings=warnings,
    )


def collect_sentiment_facts(*, ticker: str, trade_date: str | date) -> SentimentFacts:
    return SentimentFacts(
        ticker=ticker,
        trade_date=trade_date,
        unavailable_sources=["stocktwits", "reddit", "news_sentiment"],
        warnings=["Sentiment providers are not implemented in the local Phase D collector."],
    )


def _parse_trade_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _collect_ticker_news(
    *,
    yf: Any,
    ticker: str,
    start_dt: datetime,
    end_dt: datetime,
    warnings: list[str],
) -> list[NewsItem]:
    try:
        stock = yf.Ticker(ticker)
        raw_items = stock.get_news(count=TICKER_NEWS_LIMIT)
    except Exception as exc:  # pragma: no cover - depends on yfinance/network.
        warnings.append(f"yfinance ticker news failed: {exc}")
        return []

    items: list[NewsItem] = []
    for raw_item in raw_items or []:
        item = _to_news_item(raw_item)
        if not item or not _within_range(item.published_at, start_dt=start_dt, end_dt=end_dt):
            continue
        items.append(item)
    if not items:
        warnings.append(f"No yfinance ticker news found for {ticker} in the last {NEWS_LOOKBACK_DAYS} days.")
    return items


def _collect_global_news(*, yf: Any, trade_date: date, warnings: list[str]) -> list[NewsItem]:
    all_items: list[NewsItem] = []
    seen_titles: set[str] = set()
    end_dt = datetime.combine(trade_date + timedelta(days=1), time.max)

    for query in GLOBAL_NEWS_QUERIES:
        if len(all_items) >= GLOBAL_NEWS_LIMIT:
            break
        try:
            search = yf.Search(
                query=query,
                news_count=GLOBAL_NEWS_LIMIT,
                enable_fuzzy_query=True,
            )
            raw_items = getattr(search, "news", None) or []
        except Exception as exc:  # pragma: no cover - depends on yfinance/network.
            warnings.append(f"yfinance global news failed for query {query!r}: {exc}")
            continue

        for raw_item in raw_items:
            item = _to_news_item(raw_item)
            if not item:
                continue
            normalized_title = item.title.strip().casefold()
            if not normalized_title or normalized_title in seen_titles:
                continue
            if item.published_at and _as_naive(item.published_at) > end_dt:
                continue
            seen_titles.add(normalized_title)
            all_items.append(item)
            if len(all_items) >= GLOBAL_NEWS_LIMIT:
                break

    if not all_items:
        warnings.append("No yfinance global news found.")
    return all_items


def _to_news_item(raw_item: Any) -> NewsItem | None:
    if not isinstance(raw_item, dict):
        return None

    content = raw_item.get("content")
    if isinstance(content, dict):
        title = content.get("title") or raw_item.get("title")
        summary = content.get("summary") or content.get("description")
        provider = content.get("provider") if isinstance(content.get("provider"), dict) else {}
        source = provider.get("displayName") or raw_item.get("publisher")
        url = _extract_url(content) or raw_item.get("link")
        published_at = _parse_datetime(
            content.get("pubDate")
            or content.get("displayTime")
            or raw_item.get("providerPublishTime")
            or raw_item.get("pubDate")
        )
    else:
        title = raw_item.get("title")
        summary = raw_item.get("summary")
        source = raw_item.get("publisher") or raw_item.get("source")
        url = raw_item.get("link") or raw_item.get("url")
        published_at = _parse_datetime(raw_item.get("providerPublishTime") or raw_item.get("pubDate"))

    if not title:
        return None
    return NewsItem(
        title=str(title),
        published_at=published_at,
        source=str(source) if source else None,
        url=str(url) if url else None,
        summary=str(summary) if summary else None,
    )


def _extract_url(content: dict[str, Any]) -> str | None:
    for key in ("canonicalUrl", "clickThroughUrl"):
        value = content.get(key)
        if isinstance(value, dict) and value.get("url"):
            return str(value["url"])
        if isinstance(value, str):
            return value
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, int | float):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _within_range(value: datetime | None, *, start_dt: datetime, end_dt: datetime) -> bool:
    if value is None:
        return True
    naive = _as_naive(value)
    return start_dt <= naive <= end_dt


def _as_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)
