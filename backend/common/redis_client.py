from functools import lru_cache

import redis

from common.config import get_settings


@lru_cache
def get_redis() -> redis.Redis:
    # decode_responses gives str back instead of bytes
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)
