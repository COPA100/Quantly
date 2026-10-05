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


def insert_ignore(db: Session, model: type[Base], rows: Iterable[dict[str, Any]]) -> None:
    # insert rows, skipping any whose primary key already exists. shared tables
    # (prices, factors) can be filled by two jobs at once, and the loser of that
    # race must not fail its whole analysis on a duplicate key.
    rows = list(rows)
    if not rows:
        return
    dialect = postgresql if db.get_bind().dialect.name == "postgresql" else sqlite
    db.execute(dialect.insert(model).values(rows).on_conflict_do_nothing())
