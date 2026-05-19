from __future__ import annotations

from datetime import date

from stock_agents.data.yfinance_client import infer_asset_type
from stock_agents.schemas.facts import FundamentalsFacts


def collect_fundamentals_facts(*, ticker: str, trade_date: str | date, asset_type: str | None = None) -> FundamentalsFacts:
    selected_asset_type = asset_type or infer_asset_type(ticker)
    if selected_asset_type == "crypto":
        return FundamentalsFacts(
            ticker=ticker,
            trade_date=trade_date,
            asset_type="crypto",
            unavailable_reason="Company fundamentals are not available for crypto asset mode.",
            warnings=["Fundamentals analyst should be skipped by default for crypto assets."],
        )
    return FundamentalsFacts(
        ticker=ticker,
        trade_date=trade_date,
        asset_type="stock",
        company_profile={},
        financial_metrics={},
        statements={},
        unavailable_reason="Fundamentals provider is not implemented in the local Phase D collector.",
        warnings=["Fundamental facts are placeholder metadata until a real provider is configured."],
    )
