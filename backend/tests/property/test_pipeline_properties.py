"""properties of the csv -> context -> analyzers path, on the numpy implementation."""

import io
import json
import math
import random
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

import common.analytics.accelerated as accelerated
from common.analytics.analyzers import REGISTRY, run_analyzers
from common.csv_reader import parse_portfolio
from common.models import Price
from worker.analysis import _json_safe, aligned_prices, build_context
from worker.cache import holdings_digest

AS_OF = date(2026, 6, 30)
POOL = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "JPM", "V", "JNJ"]
DAYS = 60


@pytest.fixture(autouse=True)
def numpy_path(monkeypatch):
    # results must not depend on whether the c++ wheel happens to be installed
    monkeypatch.setattr(accelerated, "_engine", None)


def _series(ticker: str, days: int = DAYS) -> np.ndarray:
    # deterministic per ticker, so the same symbol always has the same history
    seed = sum(ord(c) * 31**i for i, c in enumerate(ticker)) % (2**32)
    return 100.0 * np.cumprod(1.0 + np.random.default_rng(seed).normal(0.0004, 0.015, days))


def _bars(ticker: str, closes, keep=None) -> list[Price]:
    start = AS_OF - timedelta(days=len(closes) - 1)
    return [
        Price(ticker=ticker, date=start + timedelta(days=i), close=float(c), adj_close=float(c))
        for i, c in enumerate(closes)
        if keep is None or i in keep
    ]


def _csv(rows: list[tuple[str, float, float]]) -> io.BytesIO:
    lines = ['"Positions for account Individual ...123 as of 04:00 PM ET, 2026/06/30"', ""]
    lines.append('"Symbol","Description","Qty (Quantity)","Price","Cost Basis","Security Type"')
    for symbol, qty, cost in rows:
        lines.append(f'"{symbol}","{symbol} INC","{qty}","$100.00","${cost:,.2f}","Equity"')
    lines.append('"Cash & Cash Investments","--","--","--","--","Cash and Money Market"')
    lines.append('"Account Total","","--","--","$0.00","--"')
    return io.BytesIO(("\n".join(lines) + "\n").encode())


def _analyze(rows: list[tuple[str, float, float]]) -> tuple[dict, list[dict]]:
    positions = parse_portfolio(_csv(rows))
    for p in positions:
        p["current_price"] = float(_series(str(p["symbol"]))[-1])
    symbols = dict.fromkeys(str(p["symbol"]) for p in positions)
    history = {t: _bars(t, _series(t)) for t in symbols}
    ctx = build_context(None, positions, AS_OF, history, _bars("SPY", _series("SPY")))
    return _json_safe(run_analyzers(ctx, REGISTRY)), positions


def _canonical(results: dict) -> dict:
    # row order legitimately changes list order, so put every list in ticker order
    out = json.loads(json.dumps(results))
    for pos in out["allocation"]["positions"]:
        pos.pop("rank", None)
    out["allocation"]["positions"].sort(key=lambda p: p["ticker"])
    corr = out["correlation"]
    order = sorted(range(len(corr["tickers"])), key=lambda i: corr["tickers"][i])
    corr["tickers"] = [corr["tickers"][i] for i in order]
    corr["matrix"] = [[corr["matrix"][i][j] for j in order] for i in order]
    return out


def _assert_close(a, b, path="$"):
    if isinstance(b, dict):
        assert set(a) == set(b), path
        for k in b:
            _assert_close(a[k], b[k], f"{path}.{k}")
    elif isinstance(b, list):
        assert len(a) == len(b), path
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            _assert_close(x, y, f"{path}[{i}]")
    elif isinstance(b, float):
        assert math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9), f"{path}: {a} != {b}"
    else:
        assert a == b, path


holding = st.tuples(
    st.sampled_from(POOL),
    st.floats(0.5, 500.0).map(lambda q: round(q, 3)),
    st.floats(10.0, 50_000.0).map(lambda c: round(c, 2)),
)


@settings(max_examples=25)
@given(st.lists(holding, min_size=2, max_size=6, unique_by=lambda h: h[0]), st.randoms())
def test_csv_row_order_does_not_change_the_analytics(rows, rnd: random.Random):
    shuffled = rows[:]
    rnd.shuffle(shuffled)
    assume(shuffled != rows)

    base, base_positions = _analyze(rows)
    other, other_positions = _analyze(shuffled)

    _assert_close(_canonical(other), _canonical(base))
    # the cache key is order independent too, or equal books would miss each other
    assert holdings_digest(base_positions, AS_OF) == holdings_digest(other_positions, AS_OF)


@settings(max_examples=25)
@given(
    st.lists(st.sampled_from(POOL), min_size=2, max_size=5, unique=True),
    st.data(),
)
def test_a_dropped_day_never_misaligns_returns(tickers, data):
    closes = {t: _series(t) for t in tickers}
    victim = data.draw(st.sampled_from(tickers))
    dropped = data.draw(st.sets(st.integers(1, DAYS - 2), min_size=1, max_size=8))
    keep = {t: (set(range(DAYS)) - dropped if t == victim else set(range(DAYS))) for t in tickers}
    history = {t: _bars(t, closes[t], keep[t]) for t in tickers}
    positions = [
        {"symbol": t, "quantity": 1.0, "purchase_price": 100.0, "current_price": 100.0}
        for t in tickers
    ]
    ctx = build_context(None, positions, AS_OF, history, _bars("SPY", _series("SPY")))

    start = AS_OF - timedelta(days=DAYS - 1)
    common_idx = sorted(set(range(DAYS)) - dropped)
    common_days = [start + timedelta(days=i) for i in common_idx]

    # every column shares one index: exactly the days all tickers traded
    assert list(ctx.prices.index) == common_days
    assert list(ctx.returns.index) == common_days[1:]
    assert not ctx.returns.isna().any().any()
    # each return spans consecutive common days, so no ticker is shifted against another
    for t in tickers:
        expected = closes[t][common_idx][1:] / closes[t][common_idx][:-1] - 1.0
        np.testing.assert_allclose(ctx.returns[t].to_numpy(), expected, rtol=1e-12)
    # the book return is the weighted sum of those same aligned rows
    np.testing.assert_allclose(
        ctx.portfolio_returns.to_numpy(),
        ctx.returns.mul(ctx.weights.reindex(ctx.returns.columns), axis=1).sum(axis=1).to_numpy(),
        rtol=1e-12,
    )


@given(st.integers(2, 6), st.integers(2, 30), st.data())
def test_aligned_prices_keeps_exactly_the_shared_dates(n_series, n_days, data):
    frames = {}
    for i in range(n_series):
        days = data.draw(st.sets(st.integers(0, n_days - 1), min_size=1))
        frames[f"T{i}"] = pd.Series(
            np.arange(len(days), dtype=float) + 1.0, index=sorted(days), dtype=float
        )
    shared = set.intersection(*(set(s.index) for s in frames.values()))
    out = aligned_prices(frames)
    assert set(out.index) == shared
    assert not out.isna().any().any()
    assert list(out.index) == sorted(out.index)
