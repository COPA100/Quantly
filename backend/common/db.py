from collections.abc import Generator, Iterable
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from common.config import get_settings


class Base(DeclarativeBase):
    pass


# lazy connect, nothing touches the db until the first query
_settings = get_settings()
engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    pool_size=_settings.db_pool_size,
    max_overflow=_settings.db_max_overflow,
    pool_timeout=_settings.db_pool_timeout_seconds,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False)


def get_db() -> Generator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# stays under the lowest per-statement bind parameter limit (sqlite)
MAX_BIND_PARAMS = 30_000


def insert_ignore(db: Session, model: type[Base], rows: Iterable[dict[str, Any]]) -> None:
    # insert rows, skipping any whose primary key already exists. shared tables
    # (prices, factors) can be filled by two jobs at once, and the loser of that
    # race must not fail its whole analysis on a duplicate key.
    rows = list(rows)
    if not rows:
        return
    dialect = postgresql if db.get_bind().dialect.name == "postgresql" else sqlite
    # one statement per batch: postgres caps a statement at 65,535 bind
    # parameters and sqlite at 32,766, and 20 years of daily rows exceed both
    batch = max(1, MAX_BIND_PARAMS // len(rows[0]))
    for start in range(0, len(rows), batch):
        chunk = rows[start : start + batch]
        db.execute(dialect.insert(model).values(chunk).on_conflict_do_nothing())
