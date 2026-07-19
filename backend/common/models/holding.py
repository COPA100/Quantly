from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from common.db import Base

if TYPE_CHECKING:
    from common.models.portfolio import Portfolio


class Holding(Base):
    __tablename__ = "holdings"

    id: Mapped[int] = mapped_column(primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), index=True)
    ticker: Mapped[str] = mapped_column(String(10), index=True)
    # brokerages allow fractional shares so this cannot be an int
    shares: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    cost_basis: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    purchase_date: Mapped[date | None] = mapped_column(Date)

    portfolio: Mapped["Portfolio"] = relationship(back_populates="holdings")
