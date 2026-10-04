# ruff: noqa: F811
import json

import pytest
from test_worker_task import _drain, _listen, _seed_portfolio, wired  # noqa: F401

import worker.cache as cache
import worker.tasks as tasks
from common.analytics.analyzers import REGISTRY
from common.models import AnalyticsResult, Job, Portfolio, PortfolioStatus
from common.outbox import task_id_for_job
from worker.errors import PermanentError

# one analytics row per result key every analyzer writes
RESULT_KEYS = sum(len(a.keys) for a in REGISTRY)


@pytest.fixture(autouse=True)
def no_real_backoff(monkeypatch):
    # eager retries ignore the countdown, but keep the value cheap anyway
    monkeypatch.setattr(tasks.settings, "retry_base_seconds", 0.01)


def _flaky(monkeypatch, failures, exc):
    real = tasks.compute_analytics
    state = {"calls": 0}

    def compute(db, portfolio):
        state["calls"] += 1
        if state["calls"] <= failures:
            raise exc
        return real(db, portfolio)

    monkeypatch.setattr(tasks, "compute_analytics", compute)
    return state


def test_duplicate_delivery_while_locked_is_a_noop(wired, fake_redis):
    session_factory, _ = wired
    pid, jid = _seed_portfolio(session_factory, "task-dup")
    fake_redis.set(tasks.lock_name(pid), "other-run", px=60000)

    result = tasks.analyze_portfolio.apply(args=[pid], task_id="task-dup")

    assert result.result["status"] == "duplicate"
    db = session_factory()
    assert db.get(Portfolio, pid).status == PortfolioStatus.PENDING
    assert db.get(Job, jid).status == "queued"
    assert db.query(AnalyticsResult).filter_by(portfolio_id=pid).count() == 0
    db.close()
    # the foreign lock is untouched
    assert fake_redis.get(tasks.lock_name(pid)) == "other-run"


def test_lock_is_released_after_the_run(wired, fake_redis):
    session_factory, _ = wired
    pid, _ = _seed_portfolio(session_factory, "task-rel")
    tasks.analyze_portfolio.apply(args=[pid], task_id="task-rel")
    assert fake_redis.get(tasks.lock_name(pid)) is None


def test_redelivery_of_a_finished_job_is_a_noop(wired, monkeypatch):
    session_factory, calls = wired
    pid, jid = _seed_portfolio(session_factory, "task-twice")
    tasks.analyze_portfolio.apply(args=[pid], task_id="task-twice")
    history = calls["history"]

    again = tasks.analyze_portfolio.apply(args=[pid], task_id="task-twice")

    assert again.result["status"] == "already_done"
    assert calls["history"] == history
    db = session_factory()
    assert db.query(AnalyticsResult).filter_by(portfolio_id=pid).count() == RESULT_KEYS
    assert db.get(Job, jid).attempts == 1
    db.close()


def test_stale_run_cannot_overwrite_a_newer_one(wired, monkeypatch):
    session_factory, _ = wired
    pid, jid = _seed_portfolio(session_factory, "task-stale")
    real = tasks.compute_analytics

    def compute_then_lose_the_job(db, portfolio):
        results = real(db, portfolio)
        # a newer run claimed the job while this one was computing
        other = session_factory()
        other.get(Job, jid).run_token = "newer-run"
        other.commit()
        other.close()
        return results

    monkeypatch.setattr(tasks, "compute_analytics", compute_then_lose_the_job)
    result = tasks.analyze_portfolio.apply(args=[pid], task_id="task-stale")

    assert result.result["status"] == "stale"
    db = session_factory()
    assert db.query(AnalyticsResult).filter_by(portfolio_id=pid).count() == 0
    assert db.get(Portfolio, pid).status == PortfolioStatus.PROCESSING
    job = db.get(Job, jid)
    assert job.status == "running"
    assert job.run_token == "newer-run"
    db.close()


def test_transient_error_retries_then_succeeds(wired, monkeypatch):
    session_factory, _ = wired
    pid, jid = _seed_portfolio(session_factory, "task-flaky")
    state = _flaky(monkeypatch, failures=2, exc=ConnectionError("yahoo down"))
    pubsub = _listen(cache.get_redis(), pid)

    result = tasks.analyze_portfolio.apply(args=[pid], task_id="task-flaky")

    assert result.successful()
    assert state["calls"] == 3
    db = session_factory()
    job = db.get(Job, jid)
    assert job.status == "succeeded"
    assert job.attempts == 3
    assert job.last_error is None
    assert db.get(Portfolio, pid).status == PortfolioStatus.COMPLETE
    assert db.query(AnalyticsResult).filter_by(portfolio_id=pid).count() == RESULT_KEYS
    db.close()

    # portfolio stays processing across retries, the job shows the retrying state
    sent = _drain(pubsub)
    assert [m["status"] for m in sent] == ["processing"] * 5 + ["complete"]
    assert [m["job"]["status"] for m in sent] == [
        "running",
        "retrying",
        "running",
        "retrying",
        "running",
        "succeeded",
    ]
    assert sent[-1]["job"]["attempts"] == 3


def test_exhausted_retries_fail_the_job_and_land_in_the_dlq(wired, monkeypatch, fake_redis):
    session_factory, _ = wired
    pid, jid = _seed_portfolio(session_factory, "task-dead")
    state = _flaky(monkeypatch, failures=99, exc=ConnectionError("yahoo down"))
    pubsub = _listen(cache.get_redis(), pid)

    result = tasks.analyze_portfolio.apply(args=[pid], task_id="task-dead")

    assert result.failed()
    assert state["calls"] == 4
    db = session_factory()
    job = db.get(Job, jid)
    assert job.status == "failed"
    assert job.attempts == 4
    assert "yahoo down" in job.last_error
    assert db.get(Portfolio, pid).status == PortfolioStatus.FAILED
    db.close()

    records = [json.loads(r) for r in fake_redis.lrange(tasks.DLQ_KEY, 0, -1)]
    assert len(records) == 1
    assert records[0]["portfolio_id"] == pid
    assert records[0]["job_id"] == jid
    assert records[0]["error_type"] == "ConnectionError"

    sent = _drain(pubsub)
    assert sent[-1]["status"] == "failed"
    assert sent[-1]["job"]["status"] == "failed"
    assert sent[-1]["job"]["attempts"] == 4


def test_permanent_error_fails_fast_without_dlq(wired, monkeypatch, fake_redis):
    session_factory, _ = wired
    pid, jid = _seed_portfolio(session_factory, "task-perm")
    state = _flaky(monkeypatch, failures=99, exc=PermanentError("bad csv"))

    result = tasks.analyze_portfolio.apply(args=[pid], task_id="task-perm")

    assert result.failed()
    assert state["calls"] == 1
    db = session_factory()
    job = db.get(Job, jid)
    assert job.status == "failed"
    assert job.attempts == 1
    assert job.last_error == "bad csv"
    db.close()
    assert fake_redis.llen(tasks.DLQ_KEY) == 0


def test_redis_down_at_lock_time_is_retried_not_failed(wired, monkeypatch):
    import redis

    session_factory, _ = wired
    pid, jid = _seed_portfolio(session_factory, "task-lockdown")
    real = tasks.RedisLock.acquire
    state = {"calls": 0}

    def acquire(self):
        state["calls"] += 1
        if state["calls"] == 1:
            raise redis.ConnectionError("redis down")
        return real(self)

    monkeypatch.setattr(tasks.RedisLock, "acquire", acquire)
    result = tasks.analyze_portfolio.apply(args=[pid], task_id="task-lockdown")

    assert result.successful()
    db = session_factory()
    assert db.get(Job, jid).status == "succeeded"
    db.close()


def test_job_task_id_is_deterministic():
    assert task_id_for_job(7) == task_id_for_job(7)
    assert task_id_for_job(7) != task_id_for_job(8)
    assert len(task_id_for_job(7)) == 36
