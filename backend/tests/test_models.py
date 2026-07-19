from datetime import UTC, date, datetime
from decimal import Decimal

from common.models import AnalyticsResult, Holding, Job, Portfolio, Price, RefreshToken, User


def make_user(db_session, email="colin@example.com"):
    user = User(email=email)
    db_session.add(user)
    db_session.flush()
    return user


def make_portfolio(db_session, user):
    portfolio = Portfolio(user=user, original_filename="positions.csv", s3_key="raw/1.csv")
    db_session.add(portfolio)
    db_session.flush()
    return portfolio


def test_user_defaults(db_session):
    user = make_user(db_session)
    assert user.id is not None
    assert user.auth_provider == "local"
    assert user.hashed_password is None
    assert user.created_at is not None


def test_refresh_token_links_to_user(db_session):
    user = make_user(db_session)
    token = RefreshToken(
        user=user,
        token_hash="a" * 64,
        expires_at=datetime(2027, 1, 1, tzinfo=UTC),
    )
    db_session.add(token)
    db_session.flush()
    assert token.revoked_at is None
    assert user.refresh_tokens == [token]


def test_portfolio_starts_pending(db_session):
    portfolio = make_portfolio(db_session, make_user(db_session))
    assert portfolio.status == "pending"
    assert portfolio.user.portfolios == [portfolio]


def test_holding_belongs_to_portfolio(db_session):
    portfolio = make_portfolio(db_session, make_user(db_session))
    holding = Holding(portfolio=portfolio, ticker="AAPL", shares=Decimal("0.034"))
    db_session.add(holding)
    db_session.flush()
    assert portfolio.holdings == [holding]
    assert holding.purchase_date is None


def test_price_composite_key(db_session):
    price = Price(ticker="AAPL", date=date(2026, 7, 17), close=210.0)
    db_session.add(price)
    db_session.flush()
    fetched = db_session.get(Price, ("AAPL", date(2026, 7, 17)))
    assert fetched is price


def test_analytics_result_round_trips_json(db_session):
    portfolio = make_portfolio(db_session, make_user(db_session))
    result = AnalyticsResult(
        portfolio=portfolio,
        metric_name="sharpe",
        metric_value={"value": 0.42, "window_years": 5},
    )
    db_session.add(result)
    db_session.flush()
    db_session.refresh(result)
    assert result.metric_value == {"value": 0.42, "window_years": 5}
    assert portfolio.analytics_results == [result]


def test_job_defaults(db_session):
    portfolio = make_portfolio(db_session, make_user(db_session))
    job = Job(portfolio=portfolio)
    db_session.add(job)
    db_session.flush()
    assert job.status == "queued"
    assert job.started_at is None
    assert portfolio.jobs == [job]
