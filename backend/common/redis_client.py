from functools import lru_cache

import redis
import redis.asyncio as aioredis

from common.config import get_settings


@lru_cache
def get_redis() -> redis.Redis:
    # decode_responses gives str back instead of bytes
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def new_async_redis() -> aioredis.Redis:
    # not cached: an asyncio client is bound to the loop it first runs on, and
    # each sse stream needs its own connection for pub/sub anyway
    return aioredis.Redis.from_url(get_settings().redis_url, decode_responses=True)
