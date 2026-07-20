from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.orm import Session

from api.deps import get_current_user
from api.schemas.portfolio import PortfolioRead
from common.db import get_db
from common.models import Portfolio, User
from common.storage import Storage, get_storage

router = APIRouter(prefix="/portfolios", tags=["portfolios"])


@router.post("", status_code=201, response_model=PortfolioRead)
async def create_portfolio(
    file: UploadFile,
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[Storage, Depends(get_storage)],
    user: Annotated[User, Depends(get_current_user)],
):
    data = await file.read()

    portfolio = Portfolio(
        user_id=user.id,
        original_filename=file.filename or "portfolio.csv",
        s3_key="",
        status="pending",
    )
    db.add(portfolio)
    db.flush()  # assigns the id we need for the s3 key

    key = f"portfolios/{portfolio.id}/raw.csv"
    storage.upload_bytes(key, data)
    portfolio.s3_key = key

    db.commit()
    db.refresh(portfolio)
    return portfolio
