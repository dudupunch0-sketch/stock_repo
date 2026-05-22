from __future__ import annotations

import os
from html.parser import HTMLParser
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from stock_agents.schemas.facts import NewsFacts, NewsItem, SentimentFacts

NEWS_LOOKBACK_DAYS = 7
TICKER_NEWS_LIMIT = 20
GLOBAL_NEWS_LIMIT = 10
NAVER_FINANCE_BASE_URL = "https://finance.naver.com"
NAVER_FINANCE_NEWS_URL = f"{NAVER_FINANCE_BASE_URL}/item/news_news.naver"
NAVER_SEARCH_NEWS_URL = "https://search.naver.com/search.naver"
NAVER_FINANCE_NEWS_PAGES = 2
KST = timezone(timedelta(hours=9))
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
            warnings=["News collection disabled via STOCK_AGENTS_DISABLE_NEWS."],
        )

    start_dt = datetime.combine(parsed_date - timedelta(days=NEWS_LOOKBACK_DAYS), time.min)
    end_dt = datetime.combine(parsed_date + timedelta(days=1), time.max)
    ticker_news: list[NewsItem] = []
    naver_code = _naver_code_from_ticker(ticker)

    try:
        import yfinance as yf  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - depends on runtime environment.
        warnings.append(f"yfinance news unavailable: {exc}")
        if naver_code:
            ticker_news.extend(
                _collect_naver_ticker_news(
                    code=naver_code,
                    start_dt=start_dt,
                    end_dt=end_dt,
                    warnings=warnings,
                )
            )
        if not ticker_news:
            warnings.append(f"No ticker news found for {ticker} in the last {NEWS_LOOKBACK_DAYS} days.")
        return NewsFacts(
            ticker=ticker,
            trade_date=parsed_date,
            ticker_news=ticker_news,
            global_news=[],
            warnings=warnings,
        )

    ticker_news = _collect_yfinance_ticker_news(
        yf=yf,
        ticker=ticker,
        start_dt=start_dt,
        end_dt=end_dt,
        warnings=warnings,
    )
    if naver_code and len(ticker_news) < TICKER_NEWS_LIMIT:
        ticker_news.extend(
            _collect_naver_ticker_news(
                code=naver_code,
                start_dt=start_dt,
                end_dt=end_dt,
                warnings=warnings,
            )
        )
    ticker_news = _dedupe_news_items(ticker_news)[:TICKER_NEWS_LIMIT]
    if not ticker_news:
        warnings.append(f"No ticker news found for {ticker} in the last {NEWS_LOOKBACK_DAYS} days.")

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


def _collect_yfinance_ticker_news(
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
    return items


def _collect_naver_ticker_news(
    *,
    code: str,
    start_dt: datetime,
    end_dt: datetime,
    warnings: list[str],
) -> list[NewsItem]:
    items: list[NewsItem] = []
    for page in range(1, NAVER_FINANCE_NEWS_PAGES + 1):
        query = urlencode(
            {
                "code": code,
                "page": page,
                "sm": "title_entity_id.basic",
                "clusterId": "",
            }
        )
        try:
            html = _fetch_text(f"{NAVER_FINANCE_NEWS_URL}?{query}")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:  # pragma: no cover - network dependent.
            warnings.append(f"Naver Finance ticker news failed for {code}: {exc}")
            break

        parser = _NaverFinanceNewsParser()
        parser.feed(html)
        for item in parser.items:
            if not _within_range(item.published_at, start_dt=start_dt, end_dt=end_dt):
                continue
            items.append(item)
            if len(items) >= TICKER_NEWS_LIMIT:
                break
        if len(items) >= TICKER_NEWS_LIMIT:
            break
    if not items:
        items.extend(
            _collect_naver_search_news(
                code=code,
                start_dt=start_dt,
                end_dt=end_dt,
                warnings=warnings,
            )
        )
    return _dedupe_news_items(items)


def _collect_naver_search_news(
    *,
    code: str,
    start_dt: datetime,
    end_dt: datetime,
    warnings: list[str],
) -> list[NewsItem]:
    query = urlencode(
        {
            "where": "news",
            "query": code,
            "sort": "1",
            "pd": "3",
            "ds": _format_naver_search_date(start_dt),
            "de": _format_naver_search_date(end_dt),
        }
    )
    try:
        html = _fetch_text(f"{NAVER_SEARCH_NEWS_URL}?{query}")
    except (HTTPError, URLError, TimeoutError, OSError) as exc:  # pragma: no cover - network dependent.
        warnings.append(f"Naver Search news failed for {code}: {exc}")
        return []

    parser = _NaverSearchNewsParser()
    parser.feed(html)
    return _dedupe_news_items(parser.items)[:TICKER_NEWS_LIMIT]


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


class _NaverFinanceNewsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.items: list[NewsItem] = []
        self._in_row = False
        self._cell: str | None = None
        self._capture_title = False
        self._href: str | None = None
        self._title_parts: list[str] = []
        self._source_parts: list[str] = []
        self._date_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key: value or "" for key, value in attrs}
        if tag == "tr":
            self._in_row = True
            self._cell = None
            self._capture_title = False
            self._href = None
            self._title_parts = []
            self._source_parts = []
            self._date_parts = []
            return
        if not self._in_row:
            return
        if tag == "td":
            class_name = attrs_dict.get("class", "")
            if "title" in class_name:
                self._cell = "title"
            elif "info" in class_name:
                self._cell = "source"
            elif "date" in class_name:
                self._cell = "date"
        elif tag == "a" and self._cell == "title":
            href = attrs_dict.get("href")
            if href and "news_read" in href:
                self._href = urljoin(NAVER_FINANCE_BASE_URL, href)
                self._capture_title = True

    def handle_data(self, data: str) -> None:
        if not self._in_row:
            return
        if self._cell == "title" and self._capture_title:
            self._title_parts.append(data)
        elif self._cell == "source":
            self._source_parts.append(data)
        elif self._cell == "date":
            self._date_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self._capture_title = False
        elif tag == "td":
            self._cell = None
        elif tag == "tr" and self._in_row:
            self._finish_row()
            self._in_row = False

    def _finish_row(self) -> None:
        title = " ".join("".join(self._title_parts).split())
        if not title:
            return
        source = " ".join("".join(self._source_parts).split()) or None
        date_text = " ".join("".join(self._date_parts).split())
        self.items.append(
            NewsItem(
                title=title,
                published_at=_parse_naver_datetime(date_text),
                source=source,
                url=self._href,
                summary=None,
            )
        )


class _NaverSearchNewsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.items: list[NewsItem] = []
        self._capture_title = False
        self._href: str | None = None
        self._title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attrs_dict = {key: value or "" for key, value in attrs}
        if attrs_dict.get("data-heatmap-target") != ".tit":
            return
        self._href = attrs_dict.get("href") or None
        self._title_parts = []
        self._capture_title = True

    def handle_data(self, data: str) -> None:
        if self._capture_title:
            self._title_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or not self._capture_title:
            return
        title = " ".join("".join(self._title_parts).split())
        if title:
            self.items.append(
                NewsItem(
                    title=title,
                    published_at=None,
                    source="Naver News Search",
                    url=self._href,
                    summary=None,
                )
            )
        self._capture_title = False
        self._href = None
        self._title_parts = []


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


def _dedupe_news_items(items: list[NewsItem]) -> list[NewsItem]:
    deduped: list[NewsItem] = []
    seen: set[tuple[str, str | None]] = set()
    for item in items:
        key = (item.title.strip().casefold(), item.url)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _naver_code_from_ticker(ticker: str) -> str | None:
    base = ticker.upper().split(".", 1)[0]
    if len(base) == 6 and base.isdigit():
        return base
    return None


def _fetch_text(url: str, *, timeout: int = 10) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 stock-agents/0.1",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        raw = response.read()
        charset = response.headers.get_content_charset()
    for encoding in [charset, "utf-8", "cp949", "euc-kr"]:
        if not encoding:
            continue
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _format_naver_search_date(value: datetime) -> str:
    return _as_naive(value).date().strftime("%Y.%m.%d")


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


def _parse_naver_datetime(value: str) -> datetime | None:
    text = value.strip()
    for fmt in ("%Y.%m.%d %H:%M", "%Y.%m.%d"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.replace(tzinfo=KST)
        except ValueError:
            continue
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
