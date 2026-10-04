import datetime

from sqlalchemy import Boolean, Date, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from common.db import Base


class FactorReturn(Base):
    # fama-french daily factor returns as fractions (not percent), shared by all users
    __tablename__ = "factor_returns"

    date: Mapped[datetime.date] = mapped_column(Date, primary_key=True)
    mkt_rf: Mapped[float]
    smb: Mapped[float]
    hml: Mapped[float]
    rmw: Mapped[float]
    cma: Mapped[float]
    mom: Mapped[float]
    rf: Mapped[float]


class FactorFetch(Base):
    # when we last tried to download the factor files. keyed on the attempt, not
    # the newest stored date, because french's data lags by a month or two.
    __tablename__ = "factor_fetch"

    source: Mapped[str] = mapped_column(String(20), primary_key=True)
    attempted_at: Mapped[datetime.datetime] = mapped_column(DateTime)
    succeeded: Mapped[bool] = mapped_column(Boolean)
