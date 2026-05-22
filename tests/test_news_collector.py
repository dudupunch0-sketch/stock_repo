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
    assert facts.warnings == ["News collection disabled via STOCK_AGENTS_DISABLE_NEWS."]


def test_collect_news_facts_falls_back_to_naver_for_korean_ticker(monkeypatch):
    captured = {"urls": []}

    class FakeTicker:
        def __init__(self, ticker):
            captured["ticker"] = ticker

        def get_news(self, *, count):
            return []

    class FakeSearch:
        def __init__(self, *, query, news_count, enable_fuzzy_query):
            self.news = []

    def fake_fetch_text(url):
        captured["urls"].append(url)
        return """
        <html><body><table>
          <tr>
            <td class="title">
              <a href="/item/news_read.naver?article_id=1&amp;office_id=001&amp;code=263750">
                Pearl Abyss posts quarterly results
              </a>
            </td>
            <td class="info">Test Wire</td>
            <td class="date">2026.05.20 09:10</td>
          </tr>
          <tr>
            <td class="title">
              <a href="/item/news_read.naver?article_id=2&amp;office_id=001&amp;code=263750">
                Old Pearl Abyss article
              </a>
            </td>
            <td class="info">Test Wire</td>
            <td class="date">2026.05.01 09:10</td>
          </tr>
        </table></body></html>
        """

    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(Ticker=FakeTicker, Search=FakeSearch))
    monkeypatch.setattr("stock_agents.data.news._fetch_text", fake_fetch_text)

    facts = collect_news_facts(ticker="263750.KQ", trade_date="2026-05-22")

    assert captured["ticker"] == "263750.KQ"
    assert "code=263750" in captured["urls"][0]
    assert [item.title for item in facts.ticker_news] == ["Pearl Abyss posts quarterly results"]
    assert facts.ticker_news[0].source == "Test Wire"
    assert facts.ticker_news[0].published_at.isoformat() == "2026-05-20T09:10:00+09:00"
    assert facts.ticker_news[0].url == "https://finance.naver.com/item/news_read.naver?article_id=1&office_id=001&code=263750"
    assert "No ticker news found" not in " ".join(facts.warnings)


def test_collect_news_facts_does_not_call_naver_when_yfinance_has_enough_ticker_news(monkeypatch):
    class FakeTicker:
        def __init__(self, ticker):
            pass

        def get_news(self, *, count):
            return [
                {
                    "content": {
                        "title": f"Pearl Abyss yfinance headline {index}",
                        "provider": {"displayName": "Yahoo Finance"},
                        "canonicalUrl": {"url": f"https://example.com/{index}"},
                        "pubDate": "2026-05-20T12:00:00Z",
                    }
                }
                for index in range(count)
            ]

    class FakeSearch:
        def __init__(self, *, query, news_count, enable_fuzzy_query):
            self.news = []

    def fail_fetch_text(url):
        raise AssertionError(f"Naver fallback should not be called: {url}")

    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(Ticker=FakeTicker, Search=FakeSearch))
    monkeypatch.setattr("stock_agents.data.news._fetch_text", fail_fetch_text)

    facts = collect_news_facts(ticker="263750.KQ", trade_date="2026-05-22")

    assert len(facts.ticker_news) == 20
    assert facts.ticker_news[0].source == "Yahoo Finance"
    assert facts.ticker_news[-1].title == "Pearl Abyss yfinance headline 19"


def test_collect_news_facts_falls_back_to_naver_search(monkeypatch):
    captured = {"urls": []}

    class FakeTicker:
        def __init__(self, ticker):
            pass

        def get_news(self, *, count):
            return []

    class FakeSearch:
        def __init__(self, *, query, news_count, enable_fuzzy_query):
            self.news = []

    def fake_fetch_text(url):
        captured["urls"].append(url)
        if "news_news.naver" in url:
            return """
            <html><body><table><tr>
              <td colspan="3">No finance news</td>
            </tr></table></body></html>
            """
        return """
        <html><body>
          <a href="https://n.news.naver.com/mnews/article/001/0000000001"
             data-heatmap-target=".tit">
            Pearl Abyss search result headline
          </a>
        </body></html>
        """

    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(Ticker=FakeTicker, Search=FakeSearch))
    monkeypatch.setattr("stock_agents.data.news._fetch_text", fake_fetch_text)

    facts = collect_news_facts(ticker="263750.KQ", trade_date="2026-05-22")

    assert any("search.naver.com" in url for url in captured["urls"])
    assert [item.title for item in facts.ticker_news] == ["Pearl Abyss search result headline"]
    assert facts.ticker_news[0].source == "Naver News Search"
    assert facts.ticker_news[0].url == "https://n.news.naver.com/mnews/article/001/0000000001"
