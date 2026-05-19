from __future__ import annotations

from datetime import date

from stock_agents.schemas.facts import NewsFacts, SentimentFacts


def collect_news_facts(*, ticker: str, trade_date: str | date) -> NewsFacts:
    return NewsFacts(
        ticker=ticker,
        trade_date=trade_date,
        ticker_news=[],
        global_news=[],
        warnings=["News provider is not implemented in the local Phase D collector."],
    )


def collect_sentiment_facts(*, ticker: str, trade_date: str | date) -> SentimentFacts:
    return SentimentFacts(
        ticker=ticker,
        trade_date=trade_date,
        unavailable_sources=["stocktwits", "reddit", "news_sentiment"],
        warnings=["Sentiment providers are not implemented in the local Phase D collector."],
    )
