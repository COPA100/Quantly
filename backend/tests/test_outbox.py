import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import common.models  # noqa: F401  registers every model on the metadata
import worker.tasks as tasks
from common.db import Base
from common.models import Job, OutboxMessage, Portfolio, PortfolioStatus, User
from common.outbox import enqueue_analysis, task_id_for_job
from scripts import dlq
from worker.outbox import relay_outbox, sweep_stuck


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _portfolio_with_job(db, status=PortfolioStatus.PENDING, job_status="queued"):
    user = User(email=f"u{db.query(User).count()}@example.com", hashed_password="x")
    db.add(user)
    db.flush()
    pf = Portfolio(user_id=user.id, original_filename="p.csv", s3_key="k", status=status)
    db.add(pf)
    db.flush()
    job = Job(portfolio_id=pf.id, status=job_status)
    db.add(job)
    db.flush()
    enqueue_analysis(db, job)
    db.commit()
    return pf, job


def test_enqueue_sets_the_deterministic_task_id_and_payload(db):
    pf, job = _portfolio_with_job(db)
    assert job.celery_task_id == task_id_for_job(job.id)
    row = db.query(OutboxMessage).one()
    assert row.payload == {
        "portfolio_id": pf.id,
        "job_id": job.id,
        "task_id": job.celery_task_id,
    }
    assert row.published_at is None


def test_relay_publishes_rows_in_order_and_marks_them(db):
    _portfolio_with_job(db)
    _portfolio_with_job(db)
    sent = []

    assert relay_outbox(db, send=lambda m: sent.append(m.payload["job_id"])) == 2

    assert sent == sorted(sent) and len(sent) == 2
    rows = db.query(OutboxMessage).all()
    assert all(r.published_at is not None and r.attempts == 1 for r in rows)


def test_relay_is_idempotent_once_published(db):
    _portfolio_with_job(db)
    sent = []
    relay_outbox(db, send=sent.append)
    relay_outbox(db, send=sent.append)
    assert len(sent) == 1


def test_relay_leaves_rows_unpublished_when_the_broker_is_down(db):
    _portfolio_with_job(db)
    _portfolio_with_job(db)

    def down(message):
        raise ConnectionError("broker down")

    assert relay_outbox(db, send=down) == 0
    rows = db.query(OutboxMessage).order_by(OutboxMessage.id).all()
    assert [r.published_at for r in rows] == [None, None]
    # only the first row was attempted before the relay gave up for this tick
    assert [r.attempts for r in rows] == [1, 0]

    sent = []
    assert relay_outbox(db, send=sent.append) == 2


def test_relay_respects_batch_size(db):
    for _ in range(3):
        _portfolio_with_job(db)
    assert relay_outbox(db, send=lambda m: None, batch_size=2) == 2
    assert relay_outbox(db, send=lambda m: None, batch_size=2) == 1


def test_send_failure_after_a_partial_batch_keeps_earlier_rows_published(db):
    _portfolio_with_job(db)
    _portfolio_with_job(db)
    calls = []

    def flaky(message):
        calls.append(message.id)
        if len(calls) == 2:
            raise ConnectionError("broker down")

    assert relay_outbox(db, send=flaky) == 1
    published = [r.published_at is not None for r in db.query(OutboxMessage).order_by("id")]
    assert published == [True, False]


def _age(db, portfolio, seconds):
    portfolio.updated_at = datetime.now(UTC) - timedelta(seconds=seconds)
    db.commit()


def test_sweeper_reannounces_a_stuck_portfolio_once(db):
    pf, job = _portfolio_with_job(db)
    relay_outbox(db, send=lambda m: None)  # original message went out, then was lost
    _age(db, pf, 1000)

    assert sweep_stuck(db, stuck_after_seconds=900) == 1
    rows = db.query(OutboxMessage).order_by(OutboxMessage.id).all()
    assert len(rows) == 2
    assert rows[1].published_at is None
    assert rows[1].payload["task_id"] == job.celery_task_id

    # not stuck again until another full timeout passes
    assert sweep_stuck(db, stuck_after_seconds=900) == 0


def test_sweeper_skips_fresh_finished_and_already_queued(db):
    fresh, _ = _portfolio_with_job(db)
    done, _ = _portfolio_with_job(db, status=PortfolioStatus.COMPLETE, job_status="succeeded")
    waiting, _ = _portfolio_with_job(db)  # outbox row still unpublished
    for pf in (done, waiting):
        _age(db, pf, 5000)

    assert sweep_stuck(db, stuck_after_seconds=900) == 0
    assert fresh.status == PortfolioStatus.PENDING


def test_sweeper_catches_a_portfolio_whose_worker_died_mid_run(db):
    pf, job = _portfolio_with_job(db, status=PortfolioStatus.PROCESSING, job_status="running")
    relay_outbox(db, send=lambda m: None)
    _age(db, pf, 2000)
    assert sweep_stuck(db, stuck_after_seconds=900) == 1


def test_dlq_requeue_resets_state_and_announces_again(db, fake_redis):
    pf, job = _portfolio_with_job(db)
    relay_outbox(db, send=lambda m: None)
    job.status = "failed"
    job.attempts = 4
    job.last_error = "boom"
    pf.status = PortfolioStatus.FAILED
    pf.error_message = "boom"
    db.commit()
    record = {
        "portfolio_id": pf.id,
        "job_id": job.id,
        "task_id": job.celery_task_id,
        "error": "boom",
        "error_type": "ConnectionError",
        "failed_at": "2026-10-04T00:00:00+00:00",
    }
    fake_redis.lpush(tasks.DLQ_KEY, json.dumps(record))

    assert [r["job_id"] for r in dlq.list_records(fake_redis)] == [job.id]
    assert dlq.requeue(fake_redis, db) == 1

    db.refresh(job)
    db.refresh(pf)
    assert (job.status, job.attempts, job.last_error) == ("queued", 0, None)
    assert pf.status == PortfolioStatus.PENDING
    unpublished = db.query(OutboxMessage).filter(OutboxMessage.published_at.is_(None)).all()
    assert len(unpublished) == 1
    assert unpublished[0].payload["task_id"] == job.celery_task_id
    assert fake_redis.llen(tasks.DLQ_KEY) == 0


def test_housekeeping_runs_on_its_own_queue_and_ticks_expire():
    # a backlog of analysis jobs must not delay the relay that publishes uploads,
    # and missed ticks must not pile up behind it
    from worker.celery_app import HOUSEKEEPING_QUEUE, celery_app

    routes = celery_app.conf.task_routes
    assert routes["relay_outbox"]["queue"] == HOUSEKEEPING_QUEUE
    assert routes["sweep_stuck_portfolios"]["queue"] == HOUSEKEEPING_QUEUE
    for entry in celery_app.conf.beat_schedule.values():
        assert entry["options"]["expires"] > 0
