import hashlib
import json
from datetime import date
from typing import Any

from common.config import get_settings
from common.redis_client import get_redis


def _key(digest: str) -> str:
    return f"analytics:{digest}"


def holdings_digest(positions: list[dict], as_of: date) -> str:
    # stable fingerprint of the book on a given day. order-independent, so two
    # portfolios holding the same names+lots on the same date share one result.
    rows = sorted(
        [str(p["symbol"]).upper(), repr(p["quantity"]), repr(p["purchase_price"])]
        for p in positions
    )
    payload = json.dumps({"as_of": as_of.isoformat(), "holdings": rows}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def get_cached(digest: str) -> dict[str, Any] | None:
    raw = get_redis().get(_key(digest))
    return json.loads(raw) if raw is not None else None


def set_cached(digest: str, results: dict[str, Any]) -> None:
    ttl = get_settings().analytics_cache_ttl_seconds
    get_redis().setex(_key(digest), ttl, json.dumps(results))
