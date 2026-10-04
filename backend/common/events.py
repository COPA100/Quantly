import json
import logging
from typing import Any

from common.models import Job, Portfolio, PortfolioStatus
from common.redis_client import get_redis

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {PortfolioStatus.COMPLETE, PortfolioStatus.FAILED}


def portfolio_channel(portfolio_id: int) -> str:
    return f"portfolio:{portfolio_id}:status"


def is_terminal(status: str) -> bool:
    return status in TERMINAL_STATUSES


def status_payload(portfolio: Portfolio, job: Job | None) -> dict[str, Any]:
    # same shape as PortfolioStatusRead, so the stream and the polled endpoint agree
    return {
        "id": portfolio.id,
        "status": str(portfolio.status),
        "job": (
            None
            if job is None
            else {
                "id": job.id,
                "status": job.status,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "finished_at": job.finished_at.isoformat() if job.finished_at else None,
            }
        ),
    }


def publish_status(portfolio: Portfolio, job: Job | None) -> None:
    # best effort: the db is the source of truth and clients fall back to
    # polling, so a redis hiccup must never fail the analysis
    try:
        get_redis().publish(
            portfolio_channel(portfolio.id), json.dumps(status_payload(portfolio, job))
        )
    except Exception:
        logger.warning("could not publish status for portfolio %s", portfolio.id, exc_info=True)
