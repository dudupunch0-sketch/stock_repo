import sys
from types import SimpleNamespace

from stock_agents.data.news import collect_news_facts


def test_collect_news_facts_uses_yfinance_ticker_and_search(monkeypatch):
    captured = {"ticker_counts": [], "searches": []}

    class FakeTicker:
        def __init__(self, ticker):
            captured["ticker"] = ticker

        def get_news(self, *, count):
            captured["ticker_counts"].append(count)
            return [
                {
                    "content": {
                        "title": "NVIDIA announces new AI platform",
                        "summary": "A recent company-specific update.",
                        "provider": {"displayName": "Yahoo Finance"},
                        "canonicalUrl": {"url": "https://example.com/nvda"},
                        "pubDate": "2026-05-20T12:00:00Z",
                    }
                },
                {
                    "content": {
                        "title": "Old NVIDIA article",
                        "provider": {"displayName": "Yahoo Finance"},
                        "canonicalUrl": {"url": "https://example.com/old"},
                        "pubDate": "2026-05-01T12:00:00Z",
                    }
                },
            ]

    class FakeSearch:
        def __init__(self, *, query, news_count, enable_fuzzy_query):
            captured["searches"].append(
                {
                    "query": query,
                    "news_count": news_count,
                    "enable_fuzzy_query": enable_fuzzy_query,
                }
            )
            self.news = [
                {
                    "content": {
                        "title": "Fed keeps markets focused on rates",
                        "summary": "A macro update.",
                        "provider": {"displayName": "Macro Wire"},
                        "canonicalUrl": {"url": "https://example.com/fed"},
                        "pubDate": "2026-05-21T08:00:00Z",
                    }
                },
                {
                    "content": {
                        "title": "Fed keeps markets focused on rates",
                        "provider": {"displayName": "Duplicate Wire"},
                        "canonicalUrl": {"url": "https://example.com/duplicate"},
                        "pubDate": "2026-05-21T09:00:00Z",
                    }
                },
            ]

    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(Ticker=FakeTicker, Search=FakeSearch))

    facts = collect_news_facts(ticker="NVDA", trade_date="2026-05-22")

    assert captured["ticker"] == "NVDA"
    assert captured["ticker_counts"] == [20]
    assert captured["searches"][0]["news_count"] == 10
    assert captured["searches"][0]["enable_fuzzy_query"] is True
    assert [item.title for item in facts.ticker_news] == ["NVIDIA announces new AI platform"]
    assert facts.ticker_news[0].source == "Yahoo Finance"
    assert facts.ticker_news[0].url == "https://example.com/nvda"
    assert [item.title for item in facts.global_news] == ["Fed keeps markets focused on rates"]
    assert facts.warnings == []


def test_collect_news_facts_can_be_disabled(monkeypatch):
    monkeypatch.setenv("STOCK_AGENTS_DISABLE_NEWS", "1")

    facts = collect_news_facts(ticker="SPY", trade_date="2026-01-15")

    assert facts.ticker_news == []
    assert facts.global_news == []
    assert facts.warnings == ["yfinance news disabled via STOCK_AGENTS_DISABLE_NEWS."]
