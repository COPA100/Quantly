from sqlalchemy.orm import Session

from common.market_data.fetcher import fetch_history
from common.models import Price


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
    # fetch the full retention window and write it to the shared prices table
    ticker = ticker.upper()
    bars = fetch_history(ticker)
    store_bars(db, ticker, bars)
    return len(bars)
