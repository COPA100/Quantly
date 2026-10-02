import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import common.models  # noqa: F401  registers every model on the metadata
from api.deps import get_enqueuer
from api.main import app
from common.db import Base, get_db
from common.models import Portfolio, PortfolioStatus, User
from common.storage import get_storage
from scripts.seed import DEFAULT_CSV, Api, SeedError, seed, wait_for_analysis

EMAIL = "demo@example.com"
PASSWORD = "quantly-demo"


class FakeStorage:
    def __init__(self):
        self.objects = {}

    def upload_bytes(self, key, data, content_type="text/csv"):
        self.objects[key] = data


@pytest.fixture
def wired():
    # the real api over an in-memory sqlite db, so the seed script is exercised
    # against the same endpoints it hits on a deployed stack
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    storage = FakeStorage()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_enqueuer] = lambda: (lambda pid: f"task-{pid}")
    yield Api("", TestClient(app)), session_factory, storage
    app.dependency_overrides.clear()


def _count(session_factory, model):
    with session_factory() as db:
        return db.scalar(select(func.count()).select_from(model))


def _set_status(session_factory, portfolio_id, status, error=None):
    with session_factory() as db:
        portfolio = db.get(Portfolio, portfolio_id)
        portfolio.status = status
        portfolio.error_message = error
        db.commit()


def test_seed_creates_the_demo_user_and_uploads_the_sample_portfolio(wired):
    api, session_factory, storage = wired

    result = seed(api, EMAIL, PASSWORD, DEFAULT_CSV)

    assert result["created"] is True
    assert _count(session_factory, User) == 1
    assert _count(session_factory, Portfolio) == 1
    # the raw csv went through the normal upload path into storage
    assert storage.objects[f"portfolios/{result['portfolio_id']}/raw.csv"] == (
        DEFAULT_CSV.read_bytes()
    )


def test_seed_twice_reuses_the_user_and_portfolio(wired):
    api, session_factory, _ = wired
    first = seed(api, EMAIL, PASSWORD, DEFAULT_CSV)

    second = seed(api, EMAIL, PASSWORD, DEFAULT_CSV)

    assert second["created"] is False
    assert second["portfolio_id"] == first["portfolio_id"]
    assert _count(session_factory, User) == 1
    assert _count(session_factory, Portfolio) == 1


def test_seed_explains_when_the_demo_account_has_a_different_password(wired):
    api, _, _ = wired
    seed(api, EMAIL, PASSWORD, DEFAULT_CSV)

    with pytest.raises(SeedError, match="different password"):
        seed(api, EMAIL, "some-other-password", DEFAULT_CSV)


def test_seed_rejects_a_csv_the_api_cannot_parse(wired, tmp_path):
    api, session_factory, _ = wired
    bad = tmp_path / "bad.csv"
    bad.write_text("not,a,portfolio\n")

    with pytest.raises(SeedError, match="upload failed"):
        seed(api, EMAIL, PASSWORD, bad)
    assert _count(session_factory, Portfolio) == 0


def test_wait_returns_once_the_analysis_completes(wired):
    api, session_factory, _ = wired
    result = seed(api, EMAIL, PASSWORD, DEFAULT_CSV)
    naps = []

    def finish_on_second_poll(seconds):
        # stands in for the worker finishing while the script sleeps
        naps.append(seconds)
        if len(naps) == 2:
            _set_status(session_factory, result["portfolio_id"], PortfolioStatus.COMPLETE)

    wait_for_analysis(
        api, result["token"], result["portfolio_id"], interval=3, sleep=finish_on_second_poll
    )

    assert naps == [3, 3]


def test_wait_raises_when_the_analysis_fails(wired):
    api, session_factory, _ = wired
    result = seed(api, EMAIL, PASSWORD, DEFAULT_CSV)
    _set_status(session_factory, result["portfolio_id"], PortfolioStatus.FAILED, "no price data")

    with pytest.raises(SeedError, match="analysis failed"):
        wait_for_analysis(api, result["token"], result["portfolio_id"], sleep=lambda s: None)


def test_wait_gives_up_after_the_timeout(wired):
    api, _, _ = wired
    result = seed(api, EMAIL, PASSWORD, DEFAULT_CSV)

    # nothing ever picks the job up, so it stays pending
    with pytest.raises(SeedError, match="timed out"):
        wait_for_analysis(
            api,
            result["token"],
            result["portfolio_id"],
            timeout=10,
            interval=5,
            sleep=lambda s: None,
        )
