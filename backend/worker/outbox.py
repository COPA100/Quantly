import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from common.config import get_settings
from common.db import SessionLocal
from common.models import Job, OutboxMessage, Portfolio, PortfolioStatus
from common.outbox import ANALYZE_KIND, enqueue_analysis
from worker.celery_app import celery_app

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _send_to_broker(message: OutboxMessage) -> None:
    # the task id is fixed per job, so a message sent twice is two deliveries of
    # the same task, and the worker's lock and job status make the second a no-op
    if message.kind != ANALYZE_KIND:
        raise ValueError(f"unknown outbox kind {message.kind}")
    payload = message.payload
    celery_app.send_task(
        "analyze_portfolio", args=[payload["portfolio_id"]], task_id=payload["task_id"]
    )


def relay_outbox(
    db, send: Callable[[OutboxMessage], None] = _send_to_broker, batch_size: int = 50
) -> int:
    # at-least-once: a crash between send and commit re-sends on the next tick.
    # SKIP LOCKED lets overlapping relays take disjoint rows on postgres, sqlite
    # (tests) ignores the clause and has a single writer anyway.
    rows = db.scalars(
        select(OutboxMessage)
        .where(OutboxMessage.published_at.is_(None))
        .order_by(OutboxMessage.id)
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    ).all()
    published = 0
    for row in rows:
        row.attempts += 1
        try:
            send(row)
        except Exception:
            # broker down: leave the row unpublished, the next tick retries it
            logger.warning("could not relay outbox row %s", row.id, exc_info=True)
            break
        row.published_at = _utcnow()
        published += 1
    db.commit()
    return published


def sweep_stuck(db, stuck_after_seconds: int) -> int:
    # a portfolio idle in pending/processing past the timeout lost its message or
    # its worker. re-announce its latest job, unless one is already waiting.
    cutoff = _utcnow() - timedelta(seconds=stuck_after_seconds)
    stuck = db.scalars(
        select(Portfolio).where(
            Portfolio.status.in_([PortfolioStatus.PENDING, PortfolioStatus.PROCESSING]),
            Portfolio.updated_at < cutoff,
        )
    ).all()
    waiting = {
        m.payload.get("job_id")
        for m in db.scalars(
            select(OutboxMessage).where(
                OutboxMessage.published_at.is_(None), OutboxMessage.kind == ANALYZE_KIND
            )
        )
    }
    swept = 0
    for portfolio in stuck:
        job = db.scalar(select(Job).where(Job.portfolio_id == portfolio.id).order_by(Job.id.desc()))
        if job is None or job.status in ("succeeded", "failed"):
            continue
        if job.id in waiting:
            continue
        enqueue_analysis(db, job)
        # push the next sweep out by a full timeout
        portfolio.updated_at = _utcnow()
        swept += 1
    db.commit()
    return swept


@celery_app.task(name="relay_outbox")
def relay_outbox_task() -> int:
    db = SessionLocal()
    try:
        return relay_outbox(db, batch_size=get_settings().outbox_batch_size)
    finally:
        db.close()


@celery_app.task(name="sweep_stuck_portfolios")
def sweep_stuck_task() -> int:
    db = SessionLocal()
    try:
        return sweep_stuck(db, get_settings().stuck_after_seconds)
    finally:
        db.close()
