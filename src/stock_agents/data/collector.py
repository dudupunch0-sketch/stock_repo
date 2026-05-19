from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from stock_agents.data.fundamentals import collect_fundamentals_facts
from stock_agents.data.indicators import latest_indicator_summary
from stock_agents.data.news import collect_news_facts, collect_sentiment_facts
from stock_agents.data.yfinance_client import fetch_market_facts
from stock_agents.paths import build_run_dir, safe_ticker_component
from stock_agents.schemas.facts import FundamentalsFacts, MarketFacts, NewsFacts, SentimentFacts, TechnicalFacts


class CollectedFacts(BaseModel):
    run_dir: Path
    market_facts: MarketFacts
    technical_facts: TechnicalFacts
    fundamentals_facts: FundamentalsFacts
    news_facts: NewsFacts
    sentiment_facts: SentimentFacts
    manifest_path: Path


def collect_all_facts(
    *,
    ticker: str,
    trade_date: str,
    output_dir: str | Path = "runs",
    run_id: str | None = None,
    asset_type: str | None = None,
) -> CollectedFacts:
    safe_ticker_component(ticker)
    selected_run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = build_run_dir(output_dir, ticker=ticker, trade_date=trade_date, run_id=selected_run_id)
    inputs_dir = run_dir / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=False)

    market_facts = fetch_market_facts(ticker=ticker, trade_date=trade_date, asset_type=asset_type)
    technical_facts = latest_indicator_summary(ticker=ticker, trade_date=trade_date, bars=market_facts.ohlcv)
    fundamentals_facts = collect_fundamentals_facts(
        ticker=ticker,
        trade_date=trade_date,
        asset_type=market_facts.asset_type,
    )
    news_facts = collect_news_facts(ticker=ticker, trade_date=trade_date)
    sentiment_facts = collect_sentiment_facts(ticker=ticker, trade_date=trade_date)

    artifacts = {
        "market_facts": "inputs/market_facts.json",
        "technical_facts": "inputs/technical_facts.json",
        "fundamentals_facts": "inputs/fundamentals_facts.json",
        "news_facts": "inputs/news_facts.json",
        "sentiment_facts": "inputs/sentiment_facts.json",
    }
    _write_model(run_dir / artifacts["market_facts"], market_facts)
    _write_model(run_dir / artifacts["technical_facts"], technical_facts)
    _write_model(run_dir / artifacts["fundamentals_facts"], fundamentals_facts)
    _write_model(run_dir / artifacts["news_facts"], news_facts)
    _write_model(run_dir / artifacts["sentiment_facts"], sentiment_facts)

    manifest = {
        "ticker": ticker,
        "trade_date": trade_date,
        "run_id": selected_run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "artifacts": artifacts,
    }
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return CollectedFacts(
        run_dir=run_dir,
        market_facts=market_facts,
        technical_facts=technical_facts,
        fundamentals_facts=fundamentals_facts,
        news_facts=news_facts,
        sentiment_facts=sentiment_facts,
        manifest_path=manifest_path,
    )


def _write_model(path: Path, model: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(model.model_dump_json(indent=2) + "\n", encoding="utf-8")
