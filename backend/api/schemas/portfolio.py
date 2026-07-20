from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class HoldingRead(BaseModel):
    # from_attributes lets pydantic read straight off the sqlalchemy row
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    shares: Decimal
    cost_basis: Decimal | None
    purchase_date: date | None


class PortfolioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_filename: str
    status: str
    created_at: datetime
    updated_at: datetime


class PortfolioDetail(PortfolioRead):
    # same as the list shape plus the parsed positions
    holdings: list[HoldingRead]
