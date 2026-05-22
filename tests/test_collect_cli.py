import json
from pathlib import Path

from typer.testing import CliRunner

from stock_agents.cli import app


def test_collect_writes_minimum_fact_artifacts(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_AGENTS_DISABLE_YFINANCE", "1")
    monkeypatch.setenv("STOCK_AGENTS_DISABLE_NEWS", "1")
    runner = CliRunner()
    result = runner.invoke(app, ["collect", "SPY", "--date", "2026-01-15", "--output-dir", str(tmp_path), "--run-id", "test-run"])

    assert result.exit_code == 0, result.output
    run_dir = tmp_path / "SPY" / "2026-01-15" / "test-run"
    for relative in [
        "inputs/market_facts.json",
        "inputs/technical_facts.json",
        "inputs/fundamentals_facts.json",
        "inputs/news_facts.json",
        "inputs/sentiment_facts.json",
        "manifest.json",
    ]:
        assert (run_dir / relative).exists(), relative

    market = json.loads((run_dir / "inputs/market_facts.json").read_text())
    technical = json.loads((run_dir / "inputs/technical_facts.json").read_text())
    manifest = json.loads((run_dir / "manifest.json").read_text())

    assert market["ticker"] == "SPY"
    assert market["trade_date"] == "2026-01-15"
    assert len(market["ohlcv"]) == 252
    assert market["data_source"] == "offline_fixture"
    assert "sma_3" in technical["indicators"]
    assert "sma_200" in technical["indicators"]
    assert "rsi_14" in technical["indicators"]
    assert manifest["ticker"] == "SPY"
    assert manifest["artifacts"]["market_facts"] == "inputs/market_facts.json"


def test_collect_rejects_unsafe_ticker(tmp_path):
    runner = CliRunner()
    result = runner.invoke(app, ["collect", "../SPY", "--date", "2026-01-15", "--output-dir", str(tmp_path)])

    assert result.exit_code != 0
    assert "ticker" in result.output.lower()
