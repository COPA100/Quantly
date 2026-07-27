from datetime import date, timedelta

import fakeredis
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import common.models  # noqa: F401  registers every model on the metadata
import worker.analysis as analysis
import worker.cache as cache
import worker.tasks as tasks
from common.db import Base
from common.models import AnalyticsResult, Job, Portfolio, PortfolioStatus, Price, User

VALID_CSV = (
    b'"Positions banner"\n\n'
    b'"Symbol","Qty (Quantity)","Cost Basis"\n'
    b'"AAPL","10","$1,500.00"\n'
    b'"MSFT","2","$500.00"\n'
    b'"Cash & Cash Investments","--","--"\n'
    b'"Account Total","--","--"\n'
)

SERIES = {
    "AAPL": [100, 101, 102, 101, 103, 105, 104, 106],
    "MSFT": [50, 51, 50, 52, 53, 52, 54, 55],
    "SPY": [400, 402, 401, 403, 405, 404, 406, 408],
}

METRIC_NAMES = {
    "value",
    "gain_loss",
    "allocation",
    "volatility",
    "returns",
    "sharpe",
    "sortino",
    "drawdown",
    "beta",
    "var",
    "correlation",
    "insights",
}


class FakeStorage:
    def download_bytes(self, key):
        return VALID_CSV


def _price_series(closes, as_of):
    start = as_of - timedelta(days=len(closes) - 1)
    return [
        Price(ticker="X", date=start + timedelta(days=i), close=c, adj_close=c)
        for i, c in enumerate(closes)
    ]


@pytest.fixture
def wired(monkeypatch):
    # shared in-memory sqlite so the task's session sees seeded rows
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    monkeypatch.setattr(tasks, "SessionLocal", session_factory)

    calls = {"prices": 0, "history": 0}

    def fake_prices(tickers):
        calls["prices"] += 1
        return {t: 200.0 for t in tickers}

    def fake_history(db, ticker, as_of=None):
        calls["history"] += 1
        return _price_series(SERIES[ticker], as_of or date.today())

    monkeypatch.setattr(analysis, "get_storage", lambda: FakeStorage())
    monkeypatch.setattr(analysis, "get_current_prices", fake_prices)
    monkeypatch.setattr(analysis, "ensure_history", fake_history)
    monkeypatch.setattr(
        analysis, "ensure_benchmark", lambda db, as_of=None: _price_series(SERIES["SPY"], as_of)
    )

    # in-memory redis for the analytics cache
    client = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(cache, "get_redis", lambda: client)

    return session_factory, calls


def _seed_portfolio(session_factory, task_id):
    db = session_factory()
    user = User(email=f"{task_id}@example.com", hashed_password="x", auth_provider="local")
    db.add(user)
    db.flush()
    pf = Portfolio(user_id=user.id, original_filename="p.csv", s3_key="k", status="pending")
    db.add(pf)
    db.flush()
    job = Job(portfolio_id=pf.id, celery_task_id=task_id, status="queued")
    db.add(job)
    db.commit()
    ids = (pf.id, job.id)
    db.close()
    return ids


def test_task_completes_and_persists_every_metric(wired):
    session_factory, _ = wired
    pid, jid = _seed_portfolio(session_factory, "task-abc")

    result = tasks.analyze_portfolio.apply(args=[pid], task_id="task-abc")
    assert result.successful()

    db = session_factory()
    assert db.get(Portfolio, pid).status == PortfolioStatus.COMPLETE
    job = db.get(Job, jid)
    assert job.status == "succeeded"
    assert job.started_at is not None
    assert job.finished_at is not None
    rows = db.query(AnalyticsResult).filter_by(portfolio_id=pid).all()
    assert {r.metric_name for r in rows} == METRIC_NAMES
    db.close()


def test_missing_portfolio_marks_job_failed(wired):
    session_factory, _ = wired
    db = session_factory()
    job = Job(portfolio_id=999, celery_task_id="task-missing", status="queued")
    db.add(job)
    db.commit()
    jid = job.id
    db.close()

    result = tasks.analyze_portfolio.apply(args=[999], task_id="task-missing")
    assert result.result["status"] == "missing"

    db = session_factory()
    assert db.get(Job, jid).status == "failed"
    db.close()


def test_identical_portfolio_reuses_cached_analytics(wired):
    session_factory, calls = wired
    pid1, _ = _seed_portfolio(session_factory, "task-1")
    pid2, _ = _seed_portfolio(session_factory, "task-2")

    tasks.analyze_portfolio.apply(args=[pid1], task_id="task-1")
    history_after_first = calls["history"]
    assert history_after_first > 0

    # same holdings + same as-of day -> cache hit, no further market-data fetches
    tasks.analyze_portfolio.apply(args=[pid2], task_id="task-2")
    assert calls["history"] == history_after_first

    # the second portfolio still gets its own persisted rows
    db = session_factory()
    assert db.get(Portfolio, pid2).status == PortfolioStatus.COMPLETE
    assert db.query(AnalyticsResult).filter_by(portfolio_id=pid2).count() == len(METRIC_NAMES)
    db.close()
