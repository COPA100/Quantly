import datetime

from sqlalchemy import BigInteger, Date, String
from sqlalchemy.orm import Mapped, mapped_column

from common.db import Base


class Price(Base):
    # shared across all users, aapl history is the same no matter who holds it
    __tablename__ = "prices"

    ticker: Mapped[str] = mapped_column(String(10), primary_key=True)
    date: Mapped[datetime.date] = mapped_column(Date, primary_key=True)
    open: Mapped[float | None]
    high: Mapped[float | None]
    low: Mapped[float | None]
    close: Mapped[float]
    adj_close: Mapped[float | None]
    volume: Mapped[int | None] = mapped_column(BigInteger)
