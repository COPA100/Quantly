import time

import fakeredis
import pytest

from worker.locks import LockLostError, RedisLock


@pytest.fixture
def client():
    return fakeredis.FakeRedis(decode_responses=True)


def test_only_one_holder_at_a_time(client):
    first = RedisLock(client, "lock:a", ttl_seconds=5)
    second = RedisLock(client, "lock:a", ttl_seconds=5)
    assert first.acquire() is True
    assert second.acquire() is False


def test_release_frees_the_lock(client):
    first = RedisLock(client, "lock:a", ttl_seconds=5)
    first.acquire()
    first.release()
    assert RedisLock(client, "lock:a", ttl_seconds=5).acquire() is True


def test_release_never_deletes_another_holders_lock(client):
    stale = RedisLock(client, "lock:a", ttl_seconds=5)
    stale.acquire()
    # the stale holder's key expires and someone else takes the lock
    client.delete("lock:a")
    fresh = RedisLock(client, "lock:a", ttl_seconds=5)
    assert fresh.acquire() is True

    stale.release()
    assert client.get("lock:a") == fresh.token


def test_renew_extends_ttl_only_for_the_holder(client):
    lock = RedisLock(client, "lock:a", ttl_seconds=1)
    lock.acquire()
    client.pexpire("lock:a", 50)
    assert lock.renew() is True
    assert client.pttl("lock:a") > 500

    client.set("lock:a", "someone-else", px=1000)
    assert lock.renew() is False


def test_ensure_held_raises_after_losing_the_lock(client):
    lock = RedisLock(client, "lock:a", ttl_seconds=5)
    lock.acquire()
    lock.ensure_held()
    client.delete("lock:a")
    with pytest.raises(LockLostError):
        lock.ensure_held()


def test_expired_lock_can_be_taken_over(client):
    dead = RedisLock(client, "lock:a", ttl_seconds=0.05)
    dead.acquire()
    time.sleep(0.1)
    assert RedisLock(client, "lock:a", ttl_seconds=5).acquire() is True


def test_heartbeat_keeps_the_lock_alive_past_its_ttl(client):
    lock = RedisLock(client, "lock:a", ttl_seconds=0.3)
    assert lock.acquire()
    with lock.heartbeat():
        time.sleep(0.8)
        assert RedisLock(client, "lock:a", ttl_seconds=5).acquire() is False
        lock.ensure_held()
    lock.release()


def test_heartbeat_flags_a_lost_lock(client):
    lock = RedisLock(client, "lock:a", ttl_seconds=0.3)
    lock.acquire()
    with lock.heartbeat():
        client.delete("lock:a")
        time.sleep(0.4)
        assert lock.lost.is_set()
