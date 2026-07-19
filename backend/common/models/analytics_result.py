from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from common.db import Base

if TYPE_CHECKING:
    from common.models.portfolio import Portfolio


class AnalyticsResult(Base):
    __tablename__ = "analytics_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), index=True)
    metric_name: Mapped[str] = mapped_column(String(50))
    # jsonb on postgres so results stay queryable, plain json on sqlite in tests
    metric_value: Mapped[dict[str, Any]] = mapped_column(JSON().with_variant(JSONB(), "postgresql"))
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    portfolio: Mapped["Portfolio"] = relationship(back_populates="analytics_results")
