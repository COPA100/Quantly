import json
import logging
from datetime import UTC, datetime
from typing import Any

import redis
from sqlalchemy import delete, select, update

from common.config import get_settings
from common.db import SessionLocal
from common.events import publish_status
from common.models import AnalyticsResult, Job, Portfolio, PortfolioStatus
from common.redis_client import get_redis
from common.telemetry import record_dlq
from worker.analysis import compute_analytics
from worker.celery_app import celery_app
from worker.errors import backoff_seconds, is_transient
from worker.locks import LockLostError, RedisLock

logger = logging.getLogger(__name__)

settings = get_settings()

DLQ_KEY = "dlq:analysis"


def _utcnow() -> datetime:
    return datetime.now(UTC)


def lock_name(portfolio_id: int) -> str:
    return f"lock:analysis:{portfolio_id}"


def _persist_results(db, portfolio_id: int, results: dict[str, Any]) -> None:
    # replace any prior run so re-analyzing a portfolio is idempotent
    db.execute(delete(AnalyticsResult).where(AnalyticsResult.portfolio_id == portfolio_id))
    for metric_name, metric_value in results.items():
        db.add(
            AnalyticsResult(
                portfolio_id=portfolio_id,
                metric_name=metric_name,
                metric_value=metric_value,
            )
        )


def _job_for_task(db, task_id: str | None) -> Job | None:
    # the outbox records a Job keyed by this celery task id
    if task_id is None:
        return None
    return db.scalar(select(Job).where(Job.celery_task_id == task_id))


def _update_job(db, job_id: int | None, token: str | None, **values) -> bool:
    # a run may only write its job while it still owns the run token. a stale
    # run (lock expired, newer run started) matches no row and writes nothing.
    if job_id is None:
        return True
    stmt = update(Job).where(Job.id == job_id).values(**values)
    if token is not None:
        stmt = stmt.where(Job.run_token == token)
    return db.execute(stmt).rowcount == 1


def _publish(db, portfolio_id: int, job_id: int | None) -> None:
    # re-read after commit so the event carries what is actually stored
    db.expire_all()
    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is not None:
        publish_status(portfolio, db.get(Job, job_id) if job_id is not None else None)


def _push_dlq(portfolio_id: int, job_id: int | None, task_id: str | None, exc: Exception) -> None:
    record = {
        "portfolio_id": portfolio_id,
        "job_id": job_id,
        "task_id": task_id,
        "error": str(exc)[:500],
        "error_type": type(exc).__name__,
        "failed_at": _utcnow().isoformat(),
    }
    try:
        get_redis().lpush(DLQ_KEY, json.dumps(record))
        record_dlq()
    except redis.RedisError:
        logger.error("could not push portfolio %s to the dlq", portfolio_id, exc_info=True)


def _fail(db, portfolio_id: int, job_id: int | None, token: str | None, exc: Exception) -> bool:
    # re-fetch after the rollback so we write onto live, attached rows
    if not _update_job(
        db, job_id, token, status="failed", finished_at=_utcnow(), last_error=str(exc)[:500]
    ):
        db.rollback()
        return False
    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is not None:
        portfolio.status = PortfolioStatus.FAILED
        portfolio.error_message = str(exc)[:500]
    db.commit()
    _publish(db, portfolio_id, job_id)
    return True


def _execute(db, lock: RedisLock, portfolio: Portfolio, job: Job | None) -> dict:
    portfolio_id = portfolio.id
    job_id = job.id if job is not None else None

    if job is not None:
        job.status = "running"
        job.attempts = (job.attempts or 0) + 1
        job.run_token = lock.token
        job.started_at = _utcnow()
    portfolio.status = PortfolioStatus.PROCESSING
    db.commit()
    _publish(db, portfolio_id, job_id)

    results = compute_analytics(db, portfolio)

    # last chance to notice a lost lock before writing. the guarded job update
    # is the real fence: it matches nothing once a newer run took the token.
    lock.ensure_held()
    if not _update_job(
        db, job_id, lock.token, status="succeeded", finished_at=_utcnow(), last_error=None
    ):
        raise LockLostError(lock.name)
    _persist_results(db, portfolio_id, results)
    portfolio.status = PortfolioStatus.COMPLETE
    portfolio.error_message = None
    db.commit()
    _publish(db, portfolio_id, job_id)
    return {
        "portfolio_id": portfolio_id,
        "status": str(PortfolioStatus.COMPLETE),
        "metrics": list(results),
    }


@celery_app.task(bind=True, name="analyze_portfolio", max_retries=settings.task_max_attempts - 1)
def analyze_portfolio(self, portfolio_id: int) -> dict:
    db = SessionLocal()
    lock = RedisLock(get_redis(), lock_name(portfolio_id), settings.analysis_lock_ttl_seconds)
    started = False
    job_id: int | None = None
    task_id = self.request.id
    try:
        job = _job_for_task(db, task_id)
        job_id = job.id if job is not None else None
        portfolio = db.get(Portfolio, portfolio_id)

        if portfolio is None:
            _update_job(db, job_id, None, status="failed", finished_at=_utcnow())
            db.commit()
            return {"portfolio_id": portfolio_id, "status": "missing"}

        # redelivery of work that already finished is a no-op
        if (job is not None and job.status in ("succeeded", "failed")) or (
            job is None and portfolio.status == PortfolioStatus.COMPLETE
        ):
            return {"portfolio_id": portfolio_id, "status": "already_done"}

        # another delivery is working on this portfolio right now
        if not lock.acquire():
            return {"portfolio_id": portfolio_id, "status": "duplicate"}

        started = True
        with lock.heartbeat():
            return _execute(db, lock, portfolio, job)
    except LockLostError:
        # a newer run owns the portfolio, leave its state alone
        db.rollback()
        logger.warning("lost lock for portfolio %s, dropping stale run", portfolio_id)
        return {"portfolio_id": portfolio_id, "status": "stale"}
    except Exception as exc:
        db.rollback()
        token = lock.token if started else None
        retries = self.request.retries
        if is_transient(exc) and retries < self.max_retries:
            # portfolio stays processing, the job carries the attempt count
            if started:
                _update_job(db, job_id, token, status="retrying", last_error=str(exc)[:500])
                db.commit()
                _publish(db, portfolio_id, job_id)
            raise self.retry(
                exc=exc,
                countdown=backoff_seconds(
                    retries, settings.retry_base_seconds, settings.retry_cap_seconds
                ),
            ) from exc
        if _fail(db, portfolio_id, job_id, token, exc) and is_transient(exc):
            # retries ran out on something that looked recoverable, park it
            _push_dlq(portfolio_id, job_id, task_id, exc)
        raise
    finally:
        try:
            lock.release()
        except redis.RedisError:
            logger.warning("could not release lock for portfolio %s", portfolio_id, exc_info=True)
        db.close()
