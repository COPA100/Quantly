from datetime import date

from sqlalchemy import select

import common.market_data.history as history
from common.models import Price


def bar(day: date, close: float = 1.0) -> dict:
    return {
        "date": day,
        "open": 1.0,
        "high": 1.0,
        "low": 1.0,
        "close": close,
        "adj_close": close,
        "volume": 100,
    }


def test_first_refresh_fetches_full_window(db_session, monkeypatch):
    seen = {}

    def fake_fetch(ticker, start=None):
        seen["start"] = start
        return [bar(date(2026, 7, 20)), bar(date(2026, 7, 21))]

    monkeypatch.setattr(history, "fetch_history", fake_fetch)

    stored = history.refresh_history(db_session, "AAPL")
    assert seen["start"] is None  # full window, not a gap
    assert stored == 2


def test_incremental_only_fetches_gap_and_dedupes(db_session, monkeypatch):
    db_session.add(Price(ticker="AAPL", date=date(2026, 7, 21), close=1.0))
    db_session.flush()

    seen = {}

    def fake_fetch(ticker, start=None):
        seen["start"] = start
        # yahoo returns the boundary day we already have plus one new day
        return [bar(date(2026, 7, 21), 9.0), bar(date(2026, 7, 22), 3.0)]

    monkeypatch.setattr(history, "fetch_history", fake_fetch)

    stored = history.refresh_history(db_session, "AAPL")
    assert seen["start"] == date(2026, 7, 22)  # last stored date + 1
    assert stored == 1  # boundary duplicate filtered out

    dates = list(db_session.scalars(select(Price.date).order_by(Price.date)))
    assert dates == [date(2026, 7, 21), date(2026, 7, 22)]


def test_latest_stored_date(db_session):
    assert history.latest_stored_date(db_session, "AAPL") is None
    db_session.add(Price(ticker="AAPL", date=date(2026, 7, 10), close=1.0))
    db_session.add(Price(ticker="AAPL", date=date(2026, 7, 15), close=1.0))
    db_session.flush()
    assert history.latest_stored_date(db_session, "aapl") == date(2026, 7, 15)


def test_ensure_history_reuses_fresh_data(db_session, monkeypatch):
    as_of = date(2026, 7, 22)
    calls = {"n": 0}

    def fake_fetch(ticker, start=None):
        calls["n"] += 1
        return [bar(as_of, 5.0)]

    monkeypatch.setattr(history, "fetch_history", fake_fetch)

    history.ensure_history(db_session, "AAPL", as_of=as_of)
    history.ensure_history(db_session, "AAPL", as_of=as_of)  # already fresh
    assert calls["n"] == 1


def test_invalid_ticker_stores_nothing(db_session, monkeypatch):
    monkeypatch.setattr(history, "fetch_history", lambda ticker, start=None: [])
    result = history.ensure_history(db_session, "BADX", as_of=date(2026, 7, 22))
    assert result == []
    assert history.latest_stored_date(db_session, "BADX") is None
