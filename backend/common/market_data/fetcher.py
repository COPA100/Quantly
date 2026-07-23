# yfinance api docs: https://ranaroussi.github.io/yfinance/reference/index.html

from datetime import date

import pandas as pd
import yfinance as yf

from common.config import get_settings


def fetch_current_price(ticker: str) -> float | None:
    # latest daily close from yahoo, None for an invalid or delisted ticker
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


def fetch_history(ticker: str, start: date | None = None) -> list[dict]:
    # daily bars from yahoo, full retention window by default or since `start`
    tk = yf.Ticker(ticker)
    try:
        if start is None:
            hist = tk.history(period=f"{get_settings().history_years}y", auto_adjust=False)
        else:
            hist = tk.history(start=start.isoformat(), auto_adjust=False)
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
