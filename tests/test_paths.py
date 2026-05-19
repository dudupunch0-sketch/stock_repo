from pathlib import Path

import pytest

from stock_agents.paths import build_run_dir, safe_ticker_component


@pytest.mark.parametrize("ticker", ["SPY", "BRK.B", "BTC-USD", "7203.T", "^GSPC"])
def test_safe_ticker_component_accepts_common_market_symbols(ticker):
    assert safe_ticker_component(ticker) == ticker


@pytest.mark.parametrize("ticker", ["", ".", "..", "../SPY", "SPY/../../x", "SPY\\evil", "SPY\n", "A..B"])
def test_safe_ticker_component_rejects_path_escape_or_control_chars(ticker):
    with pytest.raises(ValueError):
        safe_ticker_component(ticker)


def test_build_run_dir_uses_safe_ticker_and_expected_layout(tmp_path):
    run_dir = build_run_dir(tmp_path, ticker="SPY", trade_date="2026-01-15", run_id="run-001")

    assert run_dir == tmp_path / "SPY" / "2026-01-15" / "run-001"
    assert run_dir.is_absolute()
