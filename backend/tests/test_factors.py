import io
import zipfile
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import select

import common.market_data.factors as mf
from common.analytics.analyzers import factors as fa
from common.analytics.context import AnalysisContext
from common.models import FactorFetch, FactorReturn

FIVE_FACTOR = """\
This file was created by CMPT_ME_BEME_OP_INV_RETS_DAILY using the 202508 CRSP database.
The 1-month TBill return is from Ibbotson and Associates, Inc.

,Mkt-RF,SMB,HML,RMW,CMA,RF
20240102,  -0.50,   0.10,  -0.20,   0.30,   0.05,  0.02
20240103,   1.00,  -0.40,   0.25,  -0.10,   0.15,  0.02
20240104, -99.99, -99.99, -99.99, -99.99, -99.99, -99.99
20240105,   0.20,   0.00,   0.10,   0.00,  -0.05,  0.02

  Annual Factors: January-December
,Mkt-RF,SMB,HML,RMW,CMA,RF
2023,  20.0,  -1.0,  -9.0,  3.0,  -7.0,  5.0

Copyright 2025 Kenneth R. French
"""

MOMENTUM = """\
Daily Momentum Factor (Mom)

  ,Mom
20240102,   0.40
20240103,  -0.30
20240105,   0.60
20240108,   0.10

Copyright 2025 Kenneth R. French
"""


def make_zip(text: str, name: str = "data.CSV") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(name, text)
    return buf.getvalue()


def row(day: date, **over) -> dict:
    base = {c: 0.001 for c in mf.COLUMNS}
    return {"date": day, **base, **over}


# parser


def test_parse_skips_junk_missing_and_annual_rows():
    rows = mf.parse_factor_csv(FIVE_FACTOR)
    assert sorted(rows) == [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 5)]
    first = rows[date(2024, 1, 2)]
    # percent in the file, fractions out
    assert first["mkt_rf"] == pytest.approx(-0.005)
    assert first["rf"] == pytest.approx(0.0002)
    assert set(first) == {"mkt_rf", "smb", "hml", "rmw", "cma", "rf"}


def test_parse_momentum_header_with_padding():
    rows = mf.parse_factor_csv(MOMENTUM)
    assert rows[date(2024, 1, 8)] == {"mom": pytest.approx(0.001)}


def test_unzip_and_merge_keeps_common_days():
    five = mf.parse_factor_csv(mf._unzip_text(make_zip(FIVE_FACTOR)))
    mom = mf.parse_factor_csv(mf._unzip_text(make_zip(MOMENTUM)))
    merged = mf.merge_factors(five, mom)
    assert [r["date"] for r in merged] == [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 5)]
    assert list(merged[0]) == ["date", *mf.COLUMNS]
    assert merged[2]["mom"] == pytest.approx(0.006)


def test_fetch_factors_reads_both_zips(monkeypatch):
    payloads = {
        mf.BASE_URL + mf.FILES[0]: make_zip(FIVE_FACTOR),
        mf.BASE_URL + mf.FILES[1]: make_zip(MOMENTUM),
    }

    class Resp:
        def __init__(self, content):
            self.content = content

        def raise_for_status(self):
            pass

    monkeypatch.setattr(mf.requests, "get", lambda url, timeout: Resp(payloads[url]))
    assert len(mf.fetch_factors()) == 3


# refresh and backoff

T0 = datetime(2026, 10, 1, 12, 0)


def test_first_refresh_stores_rows(db_session, monkeypatch):
    monkeypatch.setattr(mf, "fetch_factors", lambda: [row(date(2024, 1, 2))])
    mf.ensure_factors(db_session, now=T0)
    assert mf.latest_factor_date(db_session) == date(2024, 1, 2)


def test_fresh_attempt_is_not_refetched(db_session, monkeypatch):
    calls = []
    monkeypatch.setattr(mf, "fetch_factors", lambda: calls.append(1) or [row(date(2024, 1, 2))])
    mf.ensure_factors(db_session, now=T0)
    mf.ensure_factors(db_session, now=T0 + timedelta(days=6))
    assert len(calls) == 1


def test_stale_attempt_refetches_and_appends_only_new_days(db_session, monkeypatch):
    batches = [
        [row(date(2024, 1, 2))],
        [row(date(2024, 1, 2), mkt_rf=9.0), row(date(2024, 1, 3))],
    ]
    monkeypatch.setattr(mf, "fetch_factors", lambda: batches.pop(0))
    mf.ensure_factors(db_session, now=T0)
    mf.ensure_factors(db_session, now=T0 + timedelta(days=8))
    stored = db_session.scalars(select(FactorReturn).order_by(FactorReturn.date)).all()
    assert [r.date for r in stored] == [date(2024, 1, 2), date(2024, 1, 3)]
    assert stored[0].mkt_rf == 0.001  # existing day untouched


def test_failure_keeps_data_never_raises_and_retries_after_an_hour(db_session, monkeypatch):
    db_session.add(FactorReturn(**row(date(2024, 1, 2))))
    calls = []

    def boom():
        calls.append(1)
        raise ConnectionError("offline")

    monkeypatch.setattr(mf, "fetch_factors", boom)
    mf.ensure_factors(db_session, now=T0)  # no raise
    mf.ensure_factors(db_session, now=T0 + timedelta(minutes=30))  # backed off
    assert len(calls) == 1
    mf.ensure_factors(db_session, now=T0 + timedelta(hours=2))  # retried
    assert len(calls) == 2
    assert mf.latest_factor_date(db_session) == date(2024, 1, 2)
    assert db_session.get(FactorFetch, mf.SOURCE).succeeded is False


# newey-west


def test_newey_west_se_matches_hand_computation():
    x1 = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    y = np.array([1.1, 1.9, 3.4, 3.8, 5.3, 5.9])
    x = np.column_stack([np.ones(6), x1])
    beta, se, _ = fa.ols_newey_west(y, x, lags=1)

    # plain loops: S = sum_t u_t u_t' + w1 * sum_t (u_t u_{t-1}' + u_{t-1} u_t')
    b = np.linalg.solve(x.T @ x, x.T @ y)
    e = y - x @ b
    s = np.zeros((2, 2))
    for t in range(6):
        s += e[t] ** 2 * np.outer(x[t], x[t])
    for t in range(1, 6):
        g = e[t] * e[t - 1] * np.outer(x[t], x[t - 1])
        s += 0.5 * (g + g.T)
    bread = np.linalg.inv(x.T @ x)
    expected = np.sqrt(np.diag(bread @ s @ bread))

    assert beta == pytest.approx(b)
    assert se == pytest.approx(expected)


def test_newey_west_with_zero_lags_is_white():
    rng = np.random.default_rng(1)
    x = np.column_stack([np.ones(50), rng.normal(size=50)])
    y = x @ [0.1, 2.0] + rng.normal(size=50)
    _, se, _ = fa.ols_newey_west(y, x, lags=0)
    b = np.linalg.solve(x.T @ x, x.T @ y)
    e = y - x @ b
    bread = np.linalg.inv(x.T @ x)
    white = bread @ (x.T @ (x * (e**2)[:, None])) @ bread
    assert se == pytest.approx(np.sqrt(np.diag(white)))


# analyzer


def make_ctx(db, port: pd.Series) -> AnalysisContext:
    empty = pd.DataFrame()
    return AnalysisContext(
        as_of=date(2026, 6, 30),
        positions=[],
        total=0.0,
        weights=pd.Series(dtype=float),
        prices=empty,
        returns=empty,
        portfolio_returns=port,
        benchmark_returns=pd.Series(dtype=float),
        history={},
        full_history={},
        benchmark_ticker="SPY",
        db=db,
    )


def test_unavailable_without_db():
    port = pd.Series([0.01, 0.02], index=[date(2024, 1, 2), date(2024, 1, 3)])
    out = fa.factors.fn(make_ctx(None, port))["factors"]
    assert out["available"] is False
    assert out["reason"]


def test_unavailable_when_no_factor_data_is_stored(db_session, monkeypatch):
    # first run with the download down: nothing stored yet, the section just hides
    monkeypatch.setattr(fa, "ensure_factors", lambda db: None)
    days = [date(2024, 1, 1) + timedelta(days=i) for i in range(100)]
    out = fa.factors.fn(make_ctx(db_session, pd.Series(0.001, index=days)))["factors"]
    assert out["available"] is False
    assert "0 days" in out["reason"]


def test_unavailable_with_too_few_overlapping_days(db_session, monkeypatch):
    monkeypatch.setattr(fa, "ensure_factors", lambda db: None)
    days = [date(2024, 1, 1) + timedelta(days=i) for i in range(10)]
    for d in days:
        db_session.add(FactorReturn(**row(d)))
    db_session.flush()
    port = pd.Series(0.001, index=days)
    out = fa.factors.fn(make_ctx(db_session, port))["factors"]
    assert out["available"] is False
    assert "10" in out["reason"]


def test_regression_recovers_known_betas(db_session, monkeypatch):
    monkeypatch.setattr(fa, "ensure_factors", lambda db: None)
    rng = np.random.default_rng(42)
    n = 1500
    days = [date(2018, 1, 1) + timedelta(days=i) for i in range(n)]
    f = rng.normal(0, 0.01, size=(n, 6))
    rf = np.full(n, 0.0001)
    true = np.array([1.1, 0.5, -0.3, 0.0, 0.0, 0.4])
    port = rf + 0.0002 + f @ true + rng.normal(0, 0.002, size=n)
    for d, fr, r in zip(days, f, rf, strict=False):
        db_session.add(FactorReturn(date=d, **dict(zip(fa.FACTORS, fr, strict=False)), rf=r))
    db_session.flush()

    out = fa.factors.fn(make_ctx(db_session, pd.Series(port, index=days)))["factors"]
    assert out["available"] is True
    assert out["n_obs"] == n
    assert out["start"] == "2018-01-01"
    betas = {r["factor"]: r["beta"] for r in out["loadings"]}
    for name, want in zip(fa.FACTORS, true, strict=False):
        assert betas[name] == pytest.approx(want, abs=0.06)
    assert out["alpha_annual"] == pytest.approx(0.0002 * 252, abs=0.03)
    assert out["r_squared"] > 0.9
    mom = next(r for r in out["loadings"] if r["factor"] == "mom")
    assert mom["ci_low"] < mom["beta"] < mom["ci_high"]
    assert "momentum" in out["insight"]


def test_insight_flags_insignificant_alpha_and_no_tilt():
    loadings = [{"factor": f, "beta": 0.0, "t_stat": 0.1} for f in fa.FACTORS]
    text = fa.factor_insight(loadings, 0.01, 0.5)
    assert text == (
        "No clear style tilt beyond the market; alpha is not statistically different from zero."
    )


def test_insight_names_tilts_and_significant_alpha():
    loadings = [
        {"factor": "smb", "beta": 0.5, "t_stat": 6.0},
        {"factor": "mom", "beta": 0.4, "t_stat": 3.0},
        {"factor": "hml", "beta": -0.3, "t_stat": -2.5},
    ]
    text = fa.factor_insight(loadings, 0.034, 2.8)
    assert text.startswith("Tilted toward small caps, momentum and growth;")
    assert "3.4% a year is statistically positive" in text
