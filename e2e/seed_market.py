"""seed synthetic market data so the e2e run never calls yahoo.

there is no mock market-data source in the app yet, so this writes what the worker
would otherwise fetch: daily bars for every ticker in the sample csv plus the
benchmark, their ticker_meta rows (so the history backfill is skipped), and
current prices in the redis cache. bars run through tomorrow, so the worker's
"is the series up to date" check passes on any day, weekends included.

    cd backend && PYTHONPATH=. python ../e2e/seed_market.py

when a market_data_source=mock setting lands, drop this and set it in compose instead.
"""

from datetime import date, timedelta

import numpy as np
from sqlalchemy import delete

from common.config import get_settings
from common.db import SessionLocal
from common.market_data.history import store_bars
from common.models import Price, TickerMeta
from common.redis_client import get_redis

# the holdings in example_csv/ex1.csv
TICKERS = ["AAPL", "TSLA", "AMD", "DIS", "BAC", "SHOP", "QQQ", "VOO"]
DAYS = 400


def _bars(ticker: str, start: date) -> list[dict]:
    seed = sum(ord(c) * 31**i for i, c in enumerate(ticker)) % (2**32)
    closes = 100.0 * np.cumprod(1.0 + np.random.default_rng(seed).normal(0.0004, 0.015, DAYS))
    return [
        {
            "date": start + timedelta(days=i),
            "open": float(c),
            "high": float(c),
            "low": float(c),
            "close": float(c),
            "adj_close": float(c),
            "volume": 1_000_000,
        }
        for i, c in enumerate(closes)
    ]


def main() -> None:
    settings = get_settings()
    tickers = [*TICKERS, settings.benchmark_ticker]
    start = date.today() + timedelta(days=1) - timedelta(days=DAYS - 1)
    redis = get_redis()

    with SessionLocal() as db:
        db.execute(delete(Price).where(Price.ticker.in_(tickers)))
        db.execute(delete(TickerMeta).where(TickerMeta.ticker.in_(tickers)))
        for ticker in tickers:
            bars = _bars(ticker, start)
            store_bars(db, ticker, bars)
            db.add(TickerMeta(ticker=ticker, backfilled_from=settings.history_start))
            redis.setex(f"price:current:{ticker}", 6 * 3600, bars[-2]["close"])
        db.commit()
    print(f"seeded {len(tickers)} tickers, {DAYS} days each")


if __name__ == "__main__":
    main()
