from __future__ import annotations

import re
from pathlib import Path

_SAFE_TICKER_RE = re.compile(r"^[A-Za-z0-9^][A-Za-z0-9.^-]*$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def safe_ticker_component(ticker: str) -> str:
    """Return ticker if it is safe as a single path component."""
    if not isinstance(ticker, str):
        raise TypeError("ticker must be a string")
    if ticker in {"", ".", ".."}:
        raise ValueError("ticker must be a non-empty path component")
    if any(ch in ticker for ch in ("/", "\\", "\x00")):
        raise ValueError("ticker must not contain path separators")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in ticker):
        raise ValueError("ticker must not contain control characters")
    if ".." in ticker:
        raise ValueError("ticker must not contain parent-directory markers")
    if not _SAFE_TICKER_RE.fullmatch(ticker):
        raise ValueError(f"unsupported ticker path component: {ticker!r}")
    return ticker


def build_run_dir(base_dir: str | Path, *, ticker: str, trade_date: str, run_id: str) -> Path:
    safe_ticker = safe_ticker_component(ticker)
    if not _DATE_RE.fullmatch(trade_date):
        raise ValueError("trade_date must use YYYY-MM-DD format")
    if not _RUN_ID_RE.fullmatch(run_id) or ".." in run_id:
        raise ValueError("run_id must be a safe path component")
    return Path(base_dir).expanduser().resolve() / safe_ticker / trade_date / run_id
