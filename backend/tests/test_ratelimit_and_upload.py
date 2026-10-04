# ruff: noqa: F811
import time

import pytest
import redis
from test_portfolios_api import VALID_CSV, auth_headers, client  # noqa: F401

from api.ratelimit import check_rate_limit
from common.config import get_settings
from common.models import Job, OutboxMessage


def _upload(http, headers):
    return http.post(
        "/portfolios", files={"file": ("p.csv", VALID_CSV, "text/csv")}, headers=headers
    )


class DownRedis:
    def eval(self, *args, **kwargs):
        raise redis.ConnectionError("redis down")


def test_upload_records_job_and_outbox_row_together(client):
    http, _ = client
    headers = auth_headers(http)
    body = _upload(http, headers).json()

    from api.main import app
    from common.db import get_db

    db = next(app.dependency_overrides[get_db]())
    job = db.get(Job, body["job_id"])
    rows = db.query(OutboxMessage).all()
    assert job.status == "queued"
    assert len(rows) == 1
    assert rows[0].published_at is None
    assert rows[0].payload == {
        "portfolio_id": body["id"],
        "job_id": job.id,
        "task_id": job.celery_task_id,
    }
    db.close()


def test_upload_is_rate_limited_per_user_with_retry_after(client, monkeypatch):
    http, _ = client
    monkeypatch.setattr(get_settings(), "rate_limit_upload_max", 2)
    alice = auth_headers(http, email="alice@example.com")
    bob = auth_headers(http, email="bob@example.com")

    assert _upload(http, alice).status_code == 202
    assert _upload(http, alice).status_code == 202
    limited = _upload(http, alice)
    assert limited.status_code == 429
    assert 1 <= int(limited.headers["Retry-After"]) <= 60

    # another user has their own window
    assert _upload(http, bob).status_code == 202


def test_login_is_rate_limited_per_ip(client, monkeypatch):
    http, _ = client
    monkeypatch.setattr(get_settings(), "rate_limit_login_max", 3)
    http.post("/auth/register", json={"email": "a@example.com", "password": "hunter2pw"})
    bad = {"email": "a@example.com", "password": "wrong-password"}

    assert [http.post("/auth/login", json=bad).status_code for _ in range(3)] == [401] * 3
    blocked = http.post("/auth/login", json=bad)
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1


def test_rate_limit_can_be_disabled(client, monkeypatch):
    http, _ = client
    monkeypatch.setattr(get_settings(), "rate_limit_upload_max", 1)
    monkeypatch.setattr(get_settings(), "rate_limit_enabled", False)
    headers = auth_headers(http)
    assert [_upload(http, headers).status_code for _ in range(3)] == [202] * 3


def test_login_fails_open_when_redis_is_down(client, monkeypatch):
    http, _ = client
    http.post("/auth/register", json={"email": "a@example.com", "password": "hunter2pw"})
    monkeypatch.setattr("api.ratelimit.get_redis", lambda: DownRedis())
    resp = http.post("/auth/login", json={"email": "a@example.com", "password": "hunter2pw"})
    assert resp.status_code == 200


def test_upload_fails_closed_when_redis_is_down(client, monkeypatch):
    http, _ = client
    headers = auth_headers(http)
    monkeypatch.setattr("api.ratelimit.get_redis", lambda: DownRedis())
    resp = _upload(http, headers)
    assert resp.status_code == 503
    assert resp.headers["Retry-After"]


def test_window_slides_instead_of_resetting(fake_redis):
    key = "rl:test"
    assert check_rate_limit(fake_redis, key, 2, 1)[0] is True
    time.sleep(0.6)
    assert check_rate_limit(fake_redis, key, 2, 1)[0] is True
    allowed, retry = check_rate_limit(fake_redis, key, 2, 1)
    assert allowed is False
    assert 0 < retry <= 0.5

    # the first hit has aged out but the second has not: exactly one slot frees up
    time.sleep(0.5)
    assert check_rate_limit(fake_redis, key, 2, 1)[0] is True
    assert check_rate_limit(fake_redis, key, 2, 1)[0] is False


def test_rejected_requests_are_not_recorded(fake_redis):
    for _ in range(5):
        check_rate_limit(fake_redis, "rl:test", 2, 60)
    assert fake_redis.zcard("rl:test") == 2


def test_limit_of_one_and_independent_keys(fake_redis):
    assert check_rate_limit(fake_redis, "rl:a", 1, 60)[0] is True
    assert check_rate_limit(fake_redis, "rl:a", 1, 60)[0] is False
    assert check_rate_limit(fake_redis, "rl:b", 1, 60)[0] is True


def test_key_expires_after_the_window(fake_redis):
    check_rate_limit(fake_redis, "rl:test", 1, 1)
    assert 0 < fake_redis.pttl("rl:test") <= 1000


@pytest.mark.parametrize("bad", [0])
def test_zero_limit_always_rejects(fake_redis, bad):
    assert check_rate_limit(fake_redis, "rl:z", bad, 60)[0] is False
