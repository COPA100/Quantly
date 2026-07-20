import io
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_current_user
from api.schemas.portfolio import PortfolioDetail, PortfolioRead
from common.csv_reader import parse_portfolio
from common.db import get_db
from common.models import Holding, Portfolio, User
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

    # parse the same bytes into holding rows, str() keeps decimals exact
    for position in parse_portfolio(io.BytesIO(data)):
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
    db.refresh(portfolio)
    return portfolio


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
