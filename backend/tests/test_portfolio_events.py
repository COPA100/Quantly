import asyncio
import json

import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import common.models  # noqa: F401  registers every model on the metadata
from api.deps import get_async_redis
from api.main import app
from api.routers import portfolios as portfolios_router
from api.services.events import HEARTBEAT, status_stream
from common.db import Base, get_db
from common.events import portfolio_channel
from common.models import Job, Portfolio, PortfolioStatus, User


def _events(body: str) -> list[dict]:
    # pull the json out of every `data:` line
    return [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]


@pytest.fixture
def stream_env(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    server = fakeredis.FakeServer()

    def override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    async def override_redis():
        client = fakeredis.FakeAsyncRedis(server=server, decode_responses=True)
        try:
            yield client
        finally:
            await client.aclose()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_async_redis] = override_redis
    # short timings so a stream with no terminal event still ends the test quickly
    monkeypatch.setattr(portfolios_router.settings, "sse_heartbeat_seconds", 0.1)
    monkeypatch.setattr(portfolios_router.settings, "sse_max_seconds", 0.35)
    yield TestClient(app), factory
    app.dependency_overrides.clear()


def _login(http, email):
    http.post("/auth/register", json={"email": email, "password": "hunter2pw"})
    token = http.post("/auth/login", json={"email": email, "password": "hunter2pw"}).json()
    return {"Authorization": f"Bearer {token['access_token']}"}


def _seed(factory, email, status):
    db = factory()
    user = db.query(User).filter_by(email=email).one()
    pf = Portfolio(user_id=user.id, original_filename="p.csv", s3_key="k", status=status)
    db.add(pf)
    db.flush()
    db.add(Job(portfolio_id=pf.id, celery_task_id=f"t-{pf.id}", status="queued"))
    db.commit()
    pid = pf.id
    db.close()
    return pid


def test_events_require_auth(stream_env):
    http, _ = stream_env
    assert http.get("/portfolios/1/events").status_code == 401


def test_events_missing_or_foreign_portfolio_is_404(stream_env):
    http, factory = stream_env
    owner = _login(http, "owner@example.com")
    other = _login(http, "other@example.com")
    pid = _seed(factory, "owner@example.com", PortfolioStatus.PENDING)

    assert http.get("/portfolios/999999/events", headers=owner).status_code == 404
    assert http.get(f"/portfolios/{pid}/events", headers=other).status_code == 404


def test_events_send_current_status_first_then_heartbeats(stream_env):
    http, factory = stream_env
    headers = _login(http, "owner@example.com")
    pid = _seed(factory, "owner@example.com", PortfolioStatus.PROCESSING)

    res = http.get(f"/portfolios/{pid}/events", headers=headers)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")
    assert res.text.startswith("event: status\n")
    events = _events(res.text)
    assert events[0]["id"] == pid
    assert events[0]["status"] == "processing"
    assert events[0]["job"]["status"] == "queued"
    # nothing was published, so the stream idled on heartbeats until the cap
    assert HEARTBEAT in res.text


def test_events_close_right_away_when_already_terminal(stream_env):
    http, factory = stream_env
    headers = _login(http, "owner@example.com")
    pid = _seed(factory, "owner@example.com", PortfolioStatus.COMPLETE)

    res = http.get(f"/portfolios/{pid}/events", headers=headers)
    assert [e["status"] for e in _events(res.text)] == ["complete"]
    assert HEARTBEAT not in res.text


def _run_stream(server, snapshot, publish):
    # consume the generator while a second task publishes transitions
    async def main():
        redis = fakeredis.FakeAsyncRedis(server=server, decode_responses=True)
        chunks = []

        async def load():
            return snapshot

        async def consume():
            async for chunk in status_stream(redis, 7, load, 0.05, 5):
                chunks.append(chunk)

        async def publisher():
            await asyncio.sleep(0.2)
            for payload in publish:
                await redis.publish(portfolio_channel(7), json.dumps(payload))

        await asyncio.wait_for(asyncio.gather(consume(), publisher()), timeout=5)
        await redis.aclose()
        return chunks

    return asyncio.run(main())


def test_stream_relays_published_transitions_and_stops_on_terminal():
    server = fakeredis.FakeServer()
    snapshot = {"id": 7, "status": "pending", "job": None}
    published = [
        {"id": 7, "status": "processing", "job": None},
        {"id": 7, "status": "complete", "job": None},
        {"id": 7, "status": "processing", "job": None},  # after terminal, never read
    ]
    chunks = _run_stream(server, snapshot, published)

    statuses = [json.loads(c.split("data: ")[1])["status"] for c in chunks if c != HEARTBEAT]
    assert statuses == ["pending", "processing", "complete"]
    # the 0.2s wait before publishing spans several heartbeat intervals
    assert HEARTBEAT in chunks


def test_stream_unsubscribes_when_done():
    server = fakeredis.FakeServer()
    snapshot = {"id": 7, "status": "pending", "job": None}
    _run_stream(server, snapshot, [{"id": 7, "status": "failed", "job": None}])

    channel = portfolio_channel(7)
    sync = fakeredis.FakeRedis(server=server)
    assert dict(sync.pubsub_numsub(channel))[channel.encode()] == 0
