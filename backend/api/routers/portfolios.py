import io
from collections.abc import Callable
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_async_redis, get_current_user, get_enqueuer
from api.schemas.portfolio import (
    PortfolioAccepted,
    PortfolioDetail,
    PortfolioRead,
    PortfolioStatusRead,
)
from api.services.events import status_stream
from common.config import get_settings
from common.csv_reader import CSVValidationError, parse_portfolio
from common.db import get_db
from common.events import status_payload
from common.models import AnalyticsResult, Holding, Job, Portfolio, PortfolioStatus, User
from common.storage import Storage, get_storage

router = APIRouter(prefix="/portfolios", tags=["portfolios"])
settings = get_settings()


@router.post("", status_code=202, response_model=PortfolioAccepted)
async def create_portfolio(
    file: UploadFile,
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[Storage, Depends(get_storage)],
    user: Annotated[User, Depends(get_current_user)],
    enqueue: Annotated[Callable[[int], str], Depends(get_enqueuer)],
):
    data = await file.read()

    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="file too large")

    # parse up front so a bad file never creates a row or an s3 object
    try:
        positions = parse_portfolio(io.BytesIO(data))
    except CSVValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    portfolio = Portfolio(
        user_id=user.id,
        original_filename=file.filename or "portfolio.csv",
        s3_key="",
        status=PortfolioStatus.PENDING,
    )
    db.add(portfolio)
    db.flush()  # assigns the id we need for the s3 key

    key = f"portfolios/{portfolio.id}/raw.csv"
    storage.upload_bytes(key, data)
    portfolio.s3_key = key

    # str() keeps decimals exact when going from float to Decimal
    for position in positions:
        shares = Decimal(str(position["quantity"]))
        db.add(
            Holding(
                portfolio_id=portfolio.id,
                ticker=position["symbol"],
                shares=shares,
                cost_basis=Decimal(str(position["purchase_price"])) * shares,
            )
        )

    db.commit()

    # hand the analysis off to the worker and record the job for polling
    task_id = enqueue(portfolio.id)
    job = Job(portfolio_id=portfolio.id, celery_task_id=task_id, status="queued")
    db.add(job)
    db.commit()
    db.refresh(job)

    return PortfolioAccepted(id=portfolio.id, status=portfolio.status, job_id=job.id)


@router.get("", response_model=list[PortfolioRead])
def list_portfolios(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    return db.scalars(
        select(Portfolio).where(Portfolio.user_id == user.id).order_by(Portfolio.created_at.desc())
    ).all()


@router.get("/{portfolio_id}", response_model=PortfolioDetail)
def get_portfolio(
    portfolio_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    portfolio = db.scalar(
        select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == user.id)
    )
    if portfolio is None:
        raise HTTPException(status_code=404, detail="portfolio not found")
    return portfolio


@router.get("/{portfolio_id}/status", response_model=PortfolioStatusRead)
def get_portfolio_status(
    portfolio_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    # lightweight endpoint the client polls while analysis runs
    portfolio = db.scalar(
        select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == user.id)
    )
    if portfolio is None:
        raise HTTPException(status_code=404, detail="portfolio not found")

    latest_job = db.scalar(
        select(Job).where(Job.portfolio_id == portfolio_id).order_by(Job.id.desc())
    )
    return PortfolioStatusRead(id=portfolio.id, status=portfolio.status, job=latest_job)


@router.get("/{portfolio_id}/events")
async def stream_portfolio_status(
    portfolio_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    redis: Annotated[Redis, Depends(get_async_redis)],
):
    # server-sent status updates, replacing the client polling /status. same
    # ownership rule as /status, checked before the stream opens.
    def load() -> dict[str, Any]:
        try:
            portfolio = db.scalar(
                select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == user.id)
            )
            if portfolio is None:
                raise HTTPException(status_code=404, detail="portfolio not found")
            latest_job = db.scalar(
                select(Job).where(Job.portfolio_id == portfolio_id).order_by(Job.id.desc())
            )
            return status_payload(portfolio, latest_job)
        finally:
            # don't sit on a pooled connection for the life of the stream
            db.close()

    async def load_snapshot() -> dict[str, Any]:
        # sync db work stays off the event loop
        return await run_in_threadpool(load)

    # 404 now, while we can still send a normal response
    await load_snapshot()

    return StreamingResponse(
        status_stream(
            redis,
            portfolio_id,
            load_snapshot,
            settings.sse_heartbeat_seconds,
            settings.sse_max_seconds,
        ),
        media_type="text/event-stream",
        # no-transform and x-accel-buffering stop proxies from buffering the stream
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@router.get("/{portfolio_id}/analytics")
def get_portfolio_analytics(
    portfolio_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    # metric_name -> metric_value blob, empty until the worker finishes
    portfolio = db.scalar(
        select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == user.id)
    )
    if portfolio is None:
        raise HTTPException(status_code=404, detail="portfolio not found")

    rows = db.scalars(
        select(AnalyticsResult).where(AnalyticsResult.portfolio_id == portfolio_id)
    ).all()
    return {row.metric_name: row.metric_value for row in rows}
