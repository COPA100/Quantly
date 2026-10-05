from datetime import date, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from common.config import get_settings
from common.db import insert_ignore
from common.market_data.fetcher import fetch_history
from common.models import Price, TickerMeta


def latest_stored_date(db: Session, ticker: str) -> date | None:
    return db.scalar(select(func.max(Price.date)).where(Price.ticker == ticker.upper()))


def store_bars(db: Session, ticker: str, bars: list[dict]) -> None:
    ticker = ticker.upper()
    keys = ("date", "open", "high", "low", "close", "adj_close", "volume")
    # executes immediately, so reads later in the same job (autoflush is off in
    # the worker) see the new bars. a concurrent job storing the same ticker is
    # not an error.
    insert_ignore(db, Price, [{"ticker": ticker, **{k: bar[k] for k in keys}} for bar in bars])


def earliest_stored_date(db: Session, ticker: str) -> date | None:
    return db.scalar(select(func.min(Price.date)).where(Price.ticker == ticker.upper()))


def _mark_backfilled(db: Session, ticker: str, start: date) -> None:
    db.flush()
    insert_ignore(db, TickerMeta, [{"ticker": ticker, "backfilled_from": start}])
    db.execute(update(TickerMeta).where(TickerMeta.ticker == ticker).values(backfilled_from=start))


def refresh_history(db: Session, ticker: str) -> int:
    # first time fetch the full window, afterwards only the gap since last stored
    ticker = ticker.upper()
    last = latest_stored_date(db, ticker)
    if last is None:
        bars = fetch_history(ticker)
        if bars:
            _mark_backfilled(db, ticker, get_settings().history_start)
    else:
        bars = fetch_history(ticker, start=last + timedelta(days=1))
        # guard against yahoo handing back the boundary day we already have
        bars = [bar for bar in bars if bar["date"] > last]
    store_bars(db, ticker, bars)
    return len(bars)


def backfill_history(db: Session, ticker: str) -> int:
    # one-off: extend a ticker stored before the history start moved earlier.
    # fetches only the missing front of the series, once per ticker.
    ticker = ticker.upper()
    start = get_settings().history_start
    meta = db.get(TickerMeta, ticker)
    if meta is not None and meta.backfilled_from <= start:
        return 0
    earliest = earliest_stored_date(db, ticker)
    if earliest is None:
        return 0
    bars = []
    if earliest > start:
        bars = [b for b in fetch_history(ticker, start=start, end=earliest) if b["date"] < earliest]
        store_bars(db, ticker, bars)
    _mark_backfilled(db, ticker, start)
    return len(bars)


def get_price_history(db: Session, ticker: str) -> list[Price]:
    return db.scalars(
        select(Price).where(Price.ticker == ticker.upper()).order_by(Price.date)
    ).all()


def ensure_history(db: Session, ticker: str, as_of: date | None = None) -> list[Price]:
    # the prices table is shared, so a ticker already fetched today is reused
    # as-is. only stale or missing tickers hit yahoo again.
    as_of = as_of or date.today()
    last = latest_stored_date(db, ticker)
    if last is None or last < as_of:
        refresh_history(db, ticker)
    backfill_history(db, ticker)
    return get_price_history(db, ticker)
