from datetime import date

import fakeredis
import pytest

import worker.cache as cache


@pytest.fixture
def fake_redis(monkeypatch):
    client = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(cache, "get_redis", lambda: client)
    return client


AAPL = {"symbol": "AAPL", "quantity": 10, "purchase_price": 150.0}
MSFT = {"symbol": "msft", "quantity": 2, "purchase_price": 250.0}


def test_digest_is_order_independent():
    as_of = date(2026, 7, 25)
    assert cache.holdings_digest([AAPL, MSFT], as_of) == cache.holdings_digest([MSFT, AAPL], as_of)


def test_digest_changes_with_as_of_and_holdings():
    base = cache.holdings_digest([AAPL, MSFT], date(2026, 7, 25))
    assert base != cache.holdings_digest([AAPL, MSFT], date(2026, 7, 26))
    assert base != cache.holdings_digest([AAPL], date(2026, 7, 25))


def test_set_then_get_roundtrips(fake_redis):
    digest = cache.holdings_digest([AAPL], date(2026, 7, 25))
    assert cache.get_cached(digest) is None

    results = {"value": {"total": 2400.0}, "insights": {"beta": "Beta 1.00."}}
    cache.set_cached(digest, results)
    assert cache.get_cached(digest) == results
    # stored under the analytics namespace with a ttl
    assert fake_redis.ttl(f"analytics:{digest}") > 0
