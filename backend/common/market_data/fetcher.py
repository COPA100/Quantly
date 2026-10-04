# yfinance api docs: https://ranaroussi.github.io/yfinance/reference/index.html

from datetime import date

import pandas as pd
import yfinance as yf

from common.config import get_settings
from common.market_data.mock import mock_current_price, mock_history


def _use_mock() -> bool:
    return get_settings().market_data_source == "mock"


def fetch_current_price(ticker: str) -> float | None:
    # latest daily close from yahoo, None for an invalid or delisted ticker
    if _use_mock():
        return mock_current_price(ticker, date.today())
    try:
        hist = yf.Ticker(ticker).history(period="1d", auto_adjust=False)
    except Exception:
        # yahoo is unofficial and can throw on bad symbols or transient errors
        return None
    if hist.empty:
        return None
    return round(float(hist["Close"].iloc[-1]), 2)


def fetch_current_prices(tickers: list[str]) -> dict[str, float]:
    # one yahoo call for many tickers, missing/invalid ones are just left out
    tickers = [t.upper() for t in tickers]
    if not tickers:
        return {}
    if _use_mock():
        return {t: p for t in tickers if (p := mock_current_price(t, date.today())) is not None}
    try:
        data = yf.download(tickers, period="1d", interval="1d", progress=False, auto_adjust=False)
    except Exception:
        return {}
    if data.empty:
        return {}

    last = data["Close"].iloc[-1]
    prices = {}
    for ticker in tickers:
        # multi-ticker gives a series indexed by ticker, single gives a scalar
        value = last[ticker] if ticker in getattr(last, "index", []) else last
        if not pd.isna(value):
            prices[ticker] = round(float(value), 2)
    return prices


def _num(value) -> float | None:
    return None if pd.isna(value) else float(value)


def fetch_history(ticker: str, start: date | None = None, end: date | None = None) -> list[dict]:
    # daily bars from yahoo, from `start` (default: the configured history
    # start) up to but not including `end` (default: today)
    start = start or get_settings().history_start
    if _use_mock():
        return mock_history(ticker, start, end, date.today())
    try:
        hist = yf.Ticker(ticker).history(
            start=start.isoformat(),
            end=end.isoformat() if end is not None else None,
            auto_adjust=False,
        )
    except Exception:
        # invalid/delisted ticker or a transient yahoo error, treated as no data
        return []
    if hist.empty:
        return []

    has_adj = "Adj Close" in hist.columns
    bars = []
    for index, row in hist.iterrows():
        close = _num(row["Close"])
        bars.append(
            {
                "date": index.date(),
                "open": _num(row["Open"]),
                "high": _num(row["High"]),
                "low": _num(row["Low"]),
                "close": close,
                "adj_close": _num(row["Adj Close"]) if has_adj else close,
                "volume": None if pd.isna(row["Volume"]) else int(row["Volume"]),
            }
        )
    return bars
