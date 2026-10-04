import datetime

from sqlalchemy import Date, String
from sqlalchemy.orm import Mapped, mapped_column

from common.db import Base


class TickerMeta(Base):
    # per-ticker bookkeeping for the shared prices table
    __tablename__ = "ticker_meta"

    ticker: Mapped[str] = mapped_column(String(10), primary_key=True)
    # earliest date history has been requested back to. yahoo starts a younger
    # ticker at its listing, so this can be older than the first stored bar.
    backfilled_from: Mapped[datetime.date] = mapped_column(Date)
