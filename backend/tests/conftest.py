import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import common.models  # noqa: F401  registers every model on the metadata
from common.db import Base


@pytest.fixture(scope="session")
def db_engine():
    # in memory sqlite keeps model tests fast and independent of postgres
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    # each test runs inside a transaction that rolls back at the end
    connection = db_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()
    yield session
    session.close()
    transaction.rollback()
    connection.close()
