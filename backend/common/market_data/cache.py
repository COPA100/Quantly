from common.config import get_settings
from common.market_data.fetcher import fetch_current_price
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
