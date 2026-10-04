import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import handler  # noqa: E402

CONFIG = {
    "redis_host": "redis.internal",
    "redis_port": 6379,
    "redis_db": 1,
    "queue": "celery",
    "cluster": "quantly-dev",
    "service": "quantly-dev-worker",
}
NOW = datetime(2026, 1, 1, tzinfo=UTC)


class FakeSocket:
    def __init__(self, reply: bytes):
        self.reply = reply
        self.sent = b""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def sendall(self, data):
        self.sent += data

    def recv(self, n):
        chunk, self.reply = self.reply[:n], self.reply[n:]
        return chunk


def connector(reply: bytes):
    sock = FakeSocket(reply)
    return sock, lambda addr, timeout=None: sock


def ecs_with(running):
    ecs = MagicMock()
    ecs.describe_services.return_value = {"services": [{"runningCount": running}]}
    return ecs


def test_queue_length_speaks_resp():
    sock, connect = connector(b"+OK\r\n:42\r\n")
    assert handler.queue_length("h", 6379, 1, "celery", connect) == 42
    assert sock.sent == (b"*2\r\n$6\r\nSELECT\r\n$1\r\n1\r\n*2\r\n$4\r\nLLEN\r\n$6\r\ncelery\r\n")


def test_missing_list_is_zero():
    _, connect = connector(b"+OK\r\n:0\r\n")
    assert handler.queue_length("h", 6379, 1, "celery", connect) == 0


def test_redis_errors_raise():
    _, connect = connector(b"-ERR invalid DB index\r\n")
    with pytest.raises(handler.RedisError):
        handler.queue_length("h", 6379, 99, "celery", connect)
    _, connect = connector(b"+OK\r\n-WRONGTYPE bad\r\n")
    with pytest.raises(handler.RedisError):
        handler.queue_length("h", 6379, 1, "celery", connect)


def test_closed_connection_raises():
    _, connect = connector(b"+OK")
    with pytest.raises(handler.RedisError):
        handler.queue_length("h", 6379, 1, "celery", connect)


def test_backlog_per_worker_never_divides_by_zero():
    assert handler.backlog_per_worker(30, 3) == 10
    assert handler.backlog_per_worker(30, 0) == 30
    assert handler.backlog_per_worker(0, 0) == 0


def test_collect_publishes_both_metrics():
    _, connect = connector(b"+OK\r\n:60\r\n")
    ecs, cw = ecs_with(4), MagicMock()

    result = handler.collect(CONFIG, ecs, cw, connect, now=NOW)

    assert result == {"depth": 60, "running": 4, "backlog_per_worker": 15.0}
    ecs.describe_services.assert_called_once_with(
        cluster="quantly-dev", services=["quantly-dev-worker"]
    )
    kwargs = cw.put_metric_data.call_args.kwargs
    assert kwargs["Namespace"] == "Quantly"
    values = {m["MetricName"]: m["Value"] for m in kwargs["MetricData"]}
    assert values == {"QueueDepth": 60.0, "BacklogPerWorker": 15.0}
    assert all(
        m["Dimensions"] == [{"Name": "Service", "Value": "quantly-dev-worker"}]
        for m in kwargs["MetricData"]
    )


def test_scaled_to_zero_reports_full_depth_as_backlog():
    _, connect = connector(b"+OK\r\n:7\r\n")
    cw = MagicMock()
    result = handler.collect(CONFIG, ecs_with(0), cw, connect, now=NOW)
    assert result["backlog_per_worker"] == 7.0


def test_missing_service_raises_and_publishes_nothing():
    _, connect = connector(b"+OK\r\n:1\r\n")
    ecs, cw = MagicMock(), MagicMock()
    ecs.describe_services.return_value = {"services": []}
    with pytest.raises(RuntimeError):
        handler.collect(CONFIG, ecs, cw, connect, now=NOW)
    cw.put_metric_data.assert_not_called()


def test_config_from_env(monkeypatch):
    for key, value in {
        "REDIS_HOST": "r",
        "ECS_CLUSTER": "c",
        "ECS_SERVICE": "s",
    }.items():
        monkeypatch.setenv(key, value)
    cfg = handler.config_from_env()
    assert cfg["redis_port"] == 6379 and cfg["redis_db"] == 1 and cfg["queue"] == "celery"
