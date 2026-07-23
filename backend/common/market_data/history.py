from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from common.market_data.fetcher import fetch_history
from common.models import Price


def latest_stored_date(db: Session, ticker: str) -> date | None:
    return db.scalar(select(func.max(Price.date)).where(Price.ticker == ticker.upper()))


def store_bars(db: Session, ticker: str, bars: list[dict]) -> None:
    ticker = ticker.upper()
    for bar in bars:
        db.add(
            Price(
                ticker=ticker,
                date=bar["date"],
                open=bar["open"],
                high=bar["high"],
                low=bar["low"],
                close=bar["close"],
                adj_close=bar["adj_close"],
                volume=bar["volume"],
            )
        )


def refresh_history(db: Session, ticker: str) -> int:
    # first time fetch the full window, afterwards only the gap since last stored
    ticker = ticker.upper()
    last = latest_stored_date(db, ticker)
    if last is None:
        bars = fetch_history(ticker)
    else:
        bars = fetch_history(ticker, start=last + timedelta(days=1))
        # guard against yahoo handing back the boundary day we already have
        bars = [bar for bar in bars if bar["date"] > last]
    store_bars(db, ticker, bars)
    return len(bars)
