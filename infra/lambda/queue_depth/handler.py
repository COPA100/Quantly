"""publish celery queue depth and backlog per worker to cloudwatch.

runs every minute from eventbridge inside the vpc, so it can reach elasticache.
the broker is a plain redis list, so the depth is LLEN of the queue. redis is
spoken over a raw socket to keep the package dependency free (the lambda python
runtime ships boto3 but not redis-py).

BacklogPerWorker = depth / max(running workers, 1). the max keeps the metric
defined when the service is scaled to zero: a queued job then shows up as a
backlog of `depth`, which is what lets target tracking scale out from zero.
"""

import os
import socket
from datetime import UTC, datetime

import boto3

NAMESPACE = os.environ.get("METRIC_NAMESPACE", "Quantly")


class RedisError(Exception):
    pass


def _command(*parts: str) -> bytes:
    out = [f"*{len(parts)}\r\n".encode()]
    for part in parts:
        raw = part.encode()
        out.append(b"$%d\r\n%s\r\n" % (len(raw), raw))
    return b"".join(out)


def _read_line(sock) -> bytes:
    buf = b""
    while not buf.endswith(b"\r\n"):
        chunk = sock.recv(1)
        if not chunk:
            raise RedisError("connection closed")
        buf += chunk
    return buf[:-2]


def queue_length(
    host: str, port: int, db: int, queue: str, connect=socket.create_connection
) -> int:
    # SELECT then LLEN, replies are "+OK" and ":<n>". a missing list is 0.
    with connect((host, port), timeout=3) as sock:
        sock.sendall(_command("SELECT", str(db)) + _command("LLEN", queue))
        select = _read_line(sock)
        if not select.startswith(b"+"):
            raise RedisError(f"select failed: {select!r}")
        reply = _read_line(sock)
        if not reply.startswith(b":"):
            raise RedisError(f"llen failed: {reply!r}")
        return int(reply[1:])


def running_workers(ecs, cluster: str, service: str) -> int:
    resp = ecs.describe_services(cluster=cluster, services=[service])
    services = resp.get("services", [])
    if not services:
        raise RuntimeError(f"service {service} not found in {cluster}")
    return int(services[0]["runningCount"])


def backlog_per_worker(depth: int, running: int) -> float:
    return depth / max(running, 1)


def publish(cloudwatch, service: str, depth: int, backlog: float, now: datetime) -> None:
    dimensions = [{"Name": "Service", "Value": service}]
    cloudwatch.put_metric_data(
        Namespace=NAMESPACE,
        MetricData=[
            {
                "MetricName": "QueueDepth",
                "Dimensions": dimensions,
                "Timestamp": now,
                "Value": float(depth),
                "Unit": "Count",
            },
            {
                "MetricName": "BacklogPerWorker",
                "Dimensions": dimensions,
                "Timestamp": now,
                "Value": backlog,
                "Unit": "Count",
            },
        ],
    )


def collect(config: dict, ecs, cloudwatch, connect=socket.create_connection, now=None) -> dict:
    depth = queue_length(
        config["redis_host"], config["redis_port"], config["redis_db"], config["queue"], connect
    )
    running = running_workers(ecs, config["cluster"], config["service"])
    backlog = backlog_per_worker(depth, running)
    publish(cloudwatch, config["service"], depth, backlog, now or datetime.now(UTC))
    return {"depth": depth, "running": running, "backlog_per_worker": backlog}


def config_from_env() -> dict:
    return {
        "redis_host": os.environ["REDIS_HOST"],
        "redis_port": int(os.environ.get("REDIS_PORT", "6379")),
        "redis_db": int(os.environ.get("REDIS_DB", "1")),
        "queue": os.environ.get("QUEUE_NAME", "celery"),
        "cluster": os.environ["ECS_CLUSTER"],
        "service": os.environ["ECS_SERVICE"],
    }


def handler(event, context):
    return collect(config_from_env(), boto3.client("ecs"), boto3.client("cloudwatch"))
