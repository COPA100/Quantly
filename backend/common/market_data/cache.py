from common.config import get_settings
from common.market_data.fetcher import fetch_current_price, fetch_current_prices
from common.redis_client import get_redis


def _price_key(ticker: str) -> str:
    return f"price:current:{ticker}"


def get_current_price(ticker: str) -> float | None:
    # served from redis when warm, otherwise fetched and cached with a short ttl
    ticker = ticker.upper()
    client = get_redis()
    key = _price_key(ticker)

    cached = client.get(key)
    if cached is not None:
        return float(cached)

    price = fetch_current_price(ticker)
    if price is not None:
        client.setex(key, get_settings().current_price_ttl_seconds, price)
    return price


def get_current_prices(tickers: list[str]) -> dict[str, float]:
    # serve what redis already has, then fetch every miss in a single yahoo call
    tickers = [t.upper() for t in tickers]
    if not tickers:
        return {}
    client = get_redis()

    prices: dict[str, float] = {}
    misses: list[str] = []
    cached = client.mget([_price_key(t) for t in tickers])
    for ticker, value in zip(tickers, cached, strict=True):
        if value is not None:
            prices[ticker] = float(value)
        else:
            misses.append(ticker)

    if misses:
        ttl = get_settings().current_price_ttl_seconds
        fetched = fetch_current_prices(misses)
        pipe = client.pipeline()
        for ticker, price in fetched.items():
            pipe.setex(_price_key(ticker), ttl, price)
            prices[ticker] = price
        pipe.execute()
    return prices
