import json
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from redis.asyncio import Redis

from common.events import is_terminal, portfolio_channel


def sse_message(payload: dict[str, Any]) -> str:
    return f"event: status\ndata: {json.dumps(payload)}\n\n"


# comment line: ignored by clients, but keeps the connection from looking idle
HEARTBEAT = ": ping\n\n"


async def status_stream(
    redis: Redis,
    portfolio_id: int,
    load_snapshot: Callable[[], Awaitable[dict[str, Any]]],
    heartbeat_seconds: float,
    max_seconds: float,
) -> AsyncIterator[str]:
    # subscribe before reading the snapshot, so a transition that lands in
    # between is delivered rather than lost. a duplicate is harmless.
    channel = portfolio_channel(portfolio_id)
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)
    try:
        snapshot = await load_snapshot()
        yield sse_message(snapshot)
        if is_terminal(snapshot["status"]):
            return

        deadline = time.monotonic() + max_seconds
        while (remaining := deadline - time.monotonic()) > 0:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=min(heartbeat_seconds, remaining)
            )
            if message is None:
                yield HEARTBEAT
                continue
            payload = json.loads(message["data"])
            yield sse_message(payload)
            if is_terminal(payload["status"]):
                return
    finally:
        # also runs when the client disconnects and the task is cancelled
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
