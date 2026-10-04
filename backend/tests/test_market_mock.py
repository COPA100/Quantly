from datetime import date

import numpy as np
import pytest

from common.config import Settings
from common.market_data import fetcher
from common.market_data.mock import mock_current_price, mock_history

TODAY = date(2026, 6, 15)  # a monday


def closes(ticker, start=date(2015, 1, 1)):
    return np.array([b["close"] for b in mock_history(ticker, start, None, TODAY)])


def test_deterministic():
    assert mock_history("AAPL", date(2020, 1, 1), None, TODAY) == mock_history(
        "AAPL", date(2020, 1, 1), None, TODAY
    )


def test_slices_agree_with_full_history():
    full = {b["date"]: b for b in mock_history("MSFT", date(2010, 1, 1), None, TODAY)}
    tail = mock_history("MSFT", date(2020, 3, 2), None, TODAY)
    assert tail and all(full[b["date"]] == b for b in tail)


def test_different_tickers_differ():
    assert not np.allclose(closes("AAPL")[:50], closes("TSLA")[:50])


def test_date_range_business_days_end_exclusive():
    bars = mock_history("AAPL", date(2024, 1, 1), date(2024, 2, 1), TODAY)
    days = [b["date"] for b in bars]
    assert days[0] == date(2024, 1, 1)
    assert days[-1] == date(2024, 1, 31)
    assert all(d.weekday() < 5 for d in days)
    assert len(days) == len(set(days))


def test_default_end_includes_today():
    assert mock_history("AAPL", date(2026, 6, 1), None, TODAY)[-1]["date"] == TODAY


def test_bars_are_consistent():
    for b in mock_history("AMD", date(2022, 1, 1), None, TODAY):
        assert b["low"] <= min(b["open"], b["close"])
        assert b["high"] >= max(b["open"], b["close"])
        assert b["adj_close"] == b["close"] and b["volume"] > 0


def test_current_price_matches_last_bar():
    last = mock_history("AAPL", date(2026, 1, 1), None, TODAY)[-1]["close"]
    assert mock_current_price("aapl", TODAY) == last
    # on a weekend it is still the friday close
    sunday = date(2026, 6, 14)
    assert (
        mock_current_price("AAPL", sunday)
        == mock_history("AAPL", date(2026, 6, 12), None, sunday)[-1]["close"]
    )


def test_correlation_structure():
    rets = {t: np.diff(np.log(closes(t))) for t in ("SPY", "VOO", "AAPL", "BAC")}
    corr = np.corrcoef([rets[t] for t in rets])
    # index-like tickers track each other, single names share the market factor
    assert corr[0, 1] > 0.95
    assert 0.1 < corr[2, 3] < 0.95
    assert corr[0, 2] > 0.1
    # realistic annualised vol for a single name
    vol = rets["AAPL"].std() * np.sqrt(252)
    assert 0.12 < vol < 0.5


def test_fetcher_uses_mock_without_network(monkeypatch):
    monkeypatch.setattr(fetcher, "get_settings", lambda: Settings(market_data_source="mock"))

    def boom(*args, **kwargs):
        raise AssertionError("yahoo was called")

    monkeypatch.setattr(fetcher.yf, "Ticker", boom)
    monkeypatch.setattr(fetcher.yf, "download", boom)

    assert fetcher.fetch_history("AAPL", start=date(2024, 1, 1), end=date(2024, 1, 10))
    price = fetcher.fetch_current_price("AAPL")
    assert price is not None
    batch = fetcher.fetch_current_prices(["aapl", "SPY"])
    assert set(batch) == {"AAPL", "SPY"}


def test_default_source_is_yahoo():
    assert Settings().market_data_source == "yahoo"
    with pytest.raises(ValueError):
        Settings(market_data_source="nope")
