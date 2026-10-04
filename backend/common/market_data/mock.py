"""deterministic synthetic prices for load tests and offline runs. no network.

every ticker's path is generated from a fixed anchor date and a seed derived from
its name, so any slice (full history, incremental gap, backfill) agrees with any
other. all tickers share one market factor, which gives realistic correlations.
"""

import zlib
from datetime import date, timedelta
from functools import lru_cache

import numpy as np
import pandas as pd

ANCHOR = date(2000, 1, 3)
# fixed length so the random draws never depend on how far the caller reads
MAX_DAYS = 13_000
TRADING_DAYS = 252
MARKET_VOL = 0.16
MARKET_DRIFT = 0.07
START_PRICE = 100.0

# (beta, idiosyncratic vol) for index-like tickers so they track the market
_INDEX_LIKE = {"SPY": (1.0, 0.01), "VOO": (1.0, 0.01), "IVV": (1.0, 0.01), "QQQ": (1.15, 0.05)}


def _seed(name: str) -> int:
    return zlib.crc32(name.encode())


@lru_cache(maxsize=1)
def _days() -> pd.DatetimeIndex:
    return pd.bdate_range(ANCHOR, periods=MAX_DAYS)


@lru_cache(maxsize=1)
def _market_returns() -> np.ndarray:
    rng = np.random.default_rng(_seed("__market__"))
    daily_vol = MARKET_VOL / np.sqrt(TRADING_DAYS)
    return rng.normal(0.0, daily_vol, MAX_DAYS)


@lru_cache(maxsize=256)
def _series(ticker: str) -> pd.DataFrame:
    rng = np.random.default_rng(_seed(ticker))
    if ticker in _INDEX_LIKE:
        beta, idio_vol = _INDEX_LIKE[ticker]
        drift = MARKET_DRIFT
    else:
        beta = rng.uniform(0.5, 1.6)
        idio_vol = rng.uniform(0.10, 0.35)
        drift = rng.uniform(0.03, 0.14)

    idio = rng.normal(0.0, idio_vol / np.sqrt(TRADING_DAYS), MAX_DAYS)
    log_ret = (drift - 0.5 * (beta * MARKET_VOL) ** 2) / TRADING_DAYS + beta * _market_returns()
    log_ret = log_ret + idio
    close = START_PRICE * np.exp(np.cumsum(log_ret))
    prev = np.concatenate([[START_PRICE], close[:-1]])

    # open gaps a little from the prior close, high/low bracket the day
    spread = np.abs(rng.normal(0.0, 0.004, (MAX_DAYS, 2)))
    open_ = prev * (1 + rng.normal(0.0, 0.002, MAX_DAYS))
    high = np.maximum(open_, close) * (1 + spread[:, 0])
    low = np.minimum(open_, close) * (1 - spread[:, 1])
    volume = rng.integers(200_000, 5_000_000, MAX_DAYS)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=_days(),
    )


def mock_history(ticker: str, start: date, end: date | None, today: date) -> list[dict]:
    # bars from start up to but not including end (default: through today)
    frame = _series(ticker.upper())
    stop = end if end is not None else today + timedelta(days=1)
    window = frame.loc[pd.Timestamp(start) : pd.Timestamp(stop) - pd.Timedelta(days=1)]
    bars = []
    for index, row in window.iterrows():
        close = round(float(row["close"]), 4)
        bars.append(
            {
                "date": index.date(),
                "open": round(float(row["open"]), 4),
                "high": round(float(row["high"]), 4),
                "low": round(float(row["low"]), 4),
                "close": close,
                "adj_close": close,
                "volume": int(row["volume"]),
            }
        )
    return bars


def mock_current_price(ticker: str, today: date) -> float | None:
    # the close of the last bar on or before today, so it always matches history
    frame = _series(ticker.upper())
    window = frame.loc[: pd.Timestamp(today)]
    if window.empty:
        return None
    return round(float(window["close"].iloc[-1]), 4)
