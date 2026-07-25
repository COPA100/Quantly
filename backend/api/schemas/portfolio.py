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


class PortfolioAccepted(BaseModel):
    # 202 response: the upload is stored, analysis runs async under this job
    id: int
    status: str
    job_id: int


class JobStatusRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    started_at: datetime | None
    finished_at: datetime | None


class PortfolioStatusRead(BaseModel):
    # what the frontend polls: portfolio status plus its most recent job
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    job: JobStatusRead | None
