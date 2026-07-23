import fakeredis
import pytest

import common.market_data.cache as cache


@pytest.fixture
def fake_redis(monkeypatch):
    client = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(cache, "get_redis", lambda: client)
    return client


def test_single_price_miss_fetches_then_caches(fake_redis, monkeypatch):
    calls = {"n": 0}

    def fake_fetch(ticker):
        calls["n"] += 1
        return 150.0

    monkeypatch.setattr(cache, "fetch_current_price", fake_fetch)

    assert cache.get_current_price("aapl") == 150.0
    assert cache.get_current_price("AAPL") == 150.0  # second call hits redis
    assert calls["n"] == 1
    assert fake_redis.get("price:current:AAPL") == "150.0"


def test_missing_price_is_not_cached(fake_redis, monkeypatch):
    monkeypatch.setattr(cache, "fetch_current_price", lambda ticker: None)
    assert cache.get_current_price("BADX") is None
    assert fake_redis.get("price:current:BADX") is None


def test_batch_serves_cache_and_fetches_misses_once(fake_redis, monkeypatch):
    fake_redis.set("price:current:MSFT", 300.0)
    calls = {"args": None, "n": 0}

    def fake_batch(tickers):
        calls["n"] += 1
        calls["args"] = list(tickers)
        return {ticker: 100.0 for ticker in tickers}

    monkeypatch.setattr(cache, "fetch_current_prices", fake_batch)

    result = cache.get_current_prices(["aapl", "msft", "tsla"])
    assert result == {"MSFT": 300.0, "AAPL": 100.0, "TSLA": 100.0}
    # only one yahoo call, and only for the two that were not cached
    assert calls["n"] == 1
    assert calls["args"] == ["AAPL", "TSLA"]


def test_empty_batch_returns_empty(fake_redis):
    assert cache.get_current_prices([]) == {}
