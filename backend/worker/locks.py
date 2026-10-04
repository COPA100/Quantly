import logging
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import redis

logger = logging.getLogger(__name__)

# compare-and-delete / compare-and-extend: only the holder's token may touch the key
_RELEASE = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""

_RENEW = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('pexpire', KEYS[1], ARGV[2])
end
return 0
"""


class LockLostError(Exception):
    """the lock expired or was taken over while the holder was still working."""


class RedisLock:
    # single-instance redis lock: SET NX PX to take it, a random token to prove
    # ownership. not a fencing token, so db writes carry their own run token too.
    def __init__(self, client: redis.Redis, name: str, ttl_seconds: float):
        self.client = client
        self.name = name
        self.ttl_ms = max(int(ttl_seconds * 1000), 1)
        self.token = uuid.uuid4().hex
        self.lost = threading.Event()

    def acquire(self) -> bool:
        return bool(self.client.set(self.name, self.token, nx=True, px=self.ttl_ms))

    def renew(self) -> bool:
        return bool(self.client.eval(_RENEW, 1, self.name, self.token, self.ttl_ms))

    def release(self) -> None:
        self.client.eval(_RELEASE, 1, self.name, self.token)

    def ensure_held(self) -> None:
        # call between phases: renews synchronously and fails if ownership is gone
        if self.lost.is_set() or not self.renew():
            self.lost.set()
            raise LockLostError(self.name)

    @contextmanager
    def heartbeat(self) -> Iterator[None]:
        # renew at a third of the ttl so two beats can be missed. a transient
        # redis error is retried on the next beat, a refused renewal is final.
        stop = threading.Event()

        def beat() -> None:
            while not stop.wait(self.ttl_ms / 3000):
                try:
                    if not self.renew():
                        self.lost.set()
                        return
                except redis.RedisError:
                    logger.warning("lock heartbeat failed for %s", self.name, exc_info=True)

        thread = threading.Thread(target=beat, name=f"heartbeat-{self.name}", daemon=True)
        thread.start()
        try:
            yield
        finally:
            stop.set()
            thread.join(timeout=2)
