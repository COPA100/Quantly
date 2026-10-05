from datetime import date

import pytest
from sqlalchemy import select

import common.market_data.history as history
from common.config import get_settings
from common.models import Price, TickerMeta


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


def test_first_refresh_marks_ticker_backfilled(db_session, monkeypatch):
    monkeypatch.setattr(history, "fetch_history", lambda t, start=None: [bar(date(2026, 7, 20))])
    history.refresh_history(db_session, "AAPL")
    db_session.flush()
    meta = db_session.get(TickerMeta, "AAPL")
    assert meta.backfilled_from == get_settings().history_start


def test_backfill_fetches_only_the_missing_front_once(db_session, monkeypatch):
    # stored before the history start moved back: only the last few years exist
    db_session.add(Price(ticker="AAPL", date=date(2021, 10, 1), close=1.0))
    db_session.flush()
    calls = []

    def fake_fetch(ticker, start=None, end=None):
        calls.append((start, end))
        # yahoo end is exclusive, but return the boundary anyway to test the guard
        return [bar(date(2007, 1, 3)), bar(date(2021, 10, 1), 9.0)]

    monkeypatch.setattr(history, "fetch_history", fake_fetch)

    assert history.backfill_history(db_session, "AAPL") == 1
    assert calls == [(get_settings().history_start, date(2021, 10, 1))]
    assert history.earliest_stored_date(db_session, "AAPL") == date(2007, 1, 3)

    # already done, no second fetch
    assert history.backfill_history(db_session, "AAPL") == 0
    assert len(calls) == 1


def test_backfill_marks_young_ticker_done_even_without_older_bars(db_session, monkeypatch):
    # listed after the history start: yahoo has nothing older, don't ask again
    db_session.add(Price(ticker="NEWCO", date=date(2024, 5, 1), close=1.0))
    db_session.flush()
    calls = []
    monkeypatch.setattr(
        history, "fetch_history", lambda t, start=None, end=None: calls.append(1) or []
    )
    history.backfill_history(db_session, "NEWCO")
    history.backfill_history(db_session, "NEWCO")
    assert len(calls) == 1


def test_backfill_skips_ticker_with_no_data(db_session, monkeypatch):
    monkeypatch.setattr(history, "fetch_history", lambda *a, **k: pytest.fail("no fetch"))
    assert history.backfill_history(db_session, "BADX") == 0


def test_new_bars_are_visible_in_the_same_session_without_autoflush(db_engine, monkeypatch):
    # the worker's SessionLocal has autoflush off. a first fetch must still be
    # returned by the read that follows it, or the first analysis of a new
    # ticker silently runs without its history.
    from sqlalchemy.orm import sessionmaker

    connection = db_engine.connect()
    transaction = connection.begin()
    db = sessionmaker(bind=connection, autoflush=False)()
    try:
        monkeypatch.setattr(
            history,
            "fetch_history",
            lambda t, start=None, end=None: [bar(date(2026, 7, 20)), bar(date(2026, 7, 21))],
        )
        rows = history.ensure_history(db, "NEWT", as_of=date(2026, 7, 21))
        assert [r.date for r in rows] == [date(2026, 7, 20), date(2026, 7, 21)]
    finally:
        db.close()
        transaction.rollback()
        connection.close()


def test_storing_the_same_bars_twice_is_not_an_error(db_session):
    # two jobs fetching the same new ticker at once both insert its bars; the
    # second must skip the duplicates instead of failing its analysis
    bars = [bar(date(2026, 7, 20)), bar(date(2026, 7, 21))]
    history.store_bars(db_session, "DUPE", bars)
    history.store_bars(db_session, "DUPE", bars + [bar(date(2026, 7, 22))])
    dates = list(db_session.scalars(select(Price.date).where(Price.ticker == "DUPE")))
    assert sorted(dates) == [date(2026, 7, 20), date(2026, 7, 21), date(2026, 7, 22)]


def test_marking_backfilled_twice_updates_in_place(db_session):
    history._mark_backfilled(db_session, "DUPE", date(2010, 1, 1))
    history._mark_backfilled(db_session, "DUPE", date(2007, 1, 1))
    db_session.expire_all()
    assert db_session.get(TickerMeta, "DUPE").backfilled_from == date(2007, 1, 1)
