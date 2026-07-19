from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from common.db import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/health/db")
def health_db(db: Annotated[Session, Depends(get_db)]):
    try:
        db.execute(text("select 1"))
    except SQLAlchemyError as exc:
        # a 503 tells the load balancer the app is up but its db is not
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ok"}
