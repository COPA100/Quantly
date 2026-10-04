from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from common.db import Base

if TYPE_CHECKING:
    from common.models.portfolio import Portfolio


class Job(Base):
    # celery tracks live state in redis, this row is the durable audit trail
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), index=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(36), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    # executions started, and the error behind the latest retry or failure
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text)
    # identifies the run allowed to write results, see worker.tasks
    run_token: Mapped[str | None] = mapped_column(String(36))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    portfolio: Mapped["Portfolio"] = relationship(back_populates="jobs")
