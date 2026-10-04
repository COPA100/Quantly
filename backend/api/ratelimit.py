import logging
import math
import uuid
from typing import Annotated

import redis
from fastapi import Depends, HTTPException, Request

from api.deps import get_current_user
from common.config import get_settings
from common.models import User
from common.redis_client import get_redis

logger = logging.getLogger(__name__)

# sliding-window log in a sorted set, one script call so check and record are
# atomic across api replicas. redis TIME is the only clock, so skewed api hosts
# cannot disagree about the window. only allowed requests are recorded, which
# caps memory at `limit` entries per key.
_SLIDING_WINDOW = """
local window = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local t = redis.call('TIME')
local now = tonumber(t[1]) * 1000 + math.floor(tonumber(t[2]) / 1000)
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - window)
if redis.call('ZCARD', KEYS[1]) < limit then
    redis.call('ZADD', KEYS[1], now, ARGV[3])
    redis.call('PEXPIRE', KEYS[1], window)
    return {1, 0}
end
local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
if #oldest == 0 then
    return {0, window}
end
return {0, tonumber(oldest[2]) + window - now}
"""


def check_rate_limit(
    client: redis.Redis, key: str, limit: int, window_seconds: int
) -> tuple[bool, float]:
    # returns (allowed, seconds until the oldest counted request leaves the window)
    allowed, retry_ms = client.eval(
        _SLIDING_WINDOW, 1, key, window_seconds * 1000, limit, uuid.uuid4().hex
    )
    return bool(allowed), max(retry_ms, 0) / 1000


def _enforce(key: str, limit: int, window_seconds: int, fail_open: bool) -> None:
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return
    try:
        allowed, retry_after = check_rate_limit(get_redis(), key, limit, window_seconds)
    except redis.RedisError:
        if fail_open:
            logger.warning("rate limiter unavailable, allowing %s", key, exc_info=True)
            return
        logger.error("rate limiter unavailable, rejecting %s", key, exc_info=True)
        raise HTTPException(
            status_code=503, detail="service temporarily unavailable", headers={"Retry-After": "5"}
        ) from None
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="too many requests",
            headers={"Retry-After": str(max(math.ceil(retry_after), 1))},
        )


def limit_login(request: Request) -> None:
    # keyed by client ip because there is no user yet. behind a proxy the
    # forwarded address needs to be trusted at the server layer (uvicorn
    # --proxy-headers), not parsed here where it could be spoofed.
    # fails open: locking everyone out of login during a redis blip is worse
    # than briefly losing brute-force protection.
    settings = get_settings()
    host = request.client.host if request.client else "unknown"
    _enforce(
        f"rl:login:{host}",
        settings.rate_limit_login_max,
        settings.rate_limit_login_window_seconds,
        fail_open=True,
    )


def limit_upload(user: Annotated[User, Depends(get_current_user)]) -> None:
    # fails closed: an upload costs storage and a worker job, so without a
    # working limiter it is safer to shed the request
    settings = get_settings()
    _enforce(
        f"rl:upload:{user.id}",
        settings.rate_limit_upload_max,
        settings.rate_limit_upload_window_seconds,
        fail_open=False,
    )
