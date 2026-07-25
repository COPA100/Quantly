from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select

from common.db import SessionLocal
from common.models import AnalyticsResult, Job, Portfolio, PortfolioStatus
from worker.analysis import compute_analytics
from worker.celery_app import celery_app


def _utcnow() -> datetime:
    return datetime.now(UTC)


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
    # the enqueue endpoint records a Job keyed by this celery task id
    if task_id is None:
        return None
    return db.scalar(select(Job).where(Job.celery_task_id == task_id))


def _finish_job(db, job_id: int | None, status: str) -> None:
    if job_id is None:
        return
    job = db.get(Job, job_id)
    if job is not None:
        job.status = status
        job.finished_at = _utcnow()


def _mark_failed(db, portfolio_id: int, job_id: int | None, exc: Exception) -> None:
    # re-fetch after the rollback so we write onto live, attached rows
    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is not None:
        portfolio.status = PortfolioStatus.FAILED
        portfolio.error_message = str(exc)[:500]
    _finish_job(db, job_id, "failed")
    db.commit()


@celery_app.task(bind=True, name="analyze_portfolio")
def analyze_portfolio(self, portfolio_id: int) -> dict:
    # off-request analysis: flip portfolio + job status around the work so a
    # failure leaves both marked failed rather than stuck in processing.
    db = SessionLocal()
    try:
        job = _job_for_task(db, self.request.id)
        job_id = job.id if job is not None else None

        portfolio = db.get(Portfolio, portfolio_id)
        if portfolio is None:
            _finish_job(db, job_id, "failed")
            db.commit()
            return {"portfolio_id": portfolio_id, "status": "missing"}

        if job is not None:
            job.status = "running"
            job.started_at = _utcnow()
        portfolio.status = PortfolioStatus.PROCESSING
        db.commit()

        try:
            results = compute_analytics(db, portfolio)
            _persist_results(db, portfolio_id, results)
            portfolio.status = PortfolioStatus.COMPLETE
            portfolio.error_message = None
            _finish_job(db, job_id, "succeeded")
            db.commit()
            return {
                "portfolio_id": portfolio_id,
                "status": str(PortfolioStatus.COMPLETE),
                "metrics": list(results),
            }
        except Exception as exc:
            db.rollback()
            _mark_failed(db, portfolio_id, job_id, exc)
            raise
    finally:
        db.close()
