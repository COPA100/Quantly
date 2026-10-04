from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from common.analytics.analyzers import REGISTRY, Analyzer, run_analyzers
from common.models import Price
from worker.analysis import aligned_prices, build_context, window_start

AS_OF = date(2026, 6, 30)


def _bars(ticker: str, closes: list[float], skip: set[int] = frozenset()) -> list[Price]:
    start = AS_OF - timedelta(days=len(closes) - 1)
    return [
        Price(ticker=ticker, date=start + timedelta(days=i), close=c, adj_close=c)
        for i, c in enumerate(closes)
        if i not in skip
    ]


def _positions(*symbols: str) -> list[dict]:
    return [
        {"symbol": s, "quantity": 1.0, "purchase_price": 100.0, "current_price": 100.0}
        for s in symbols
    ]


def test_missing_day_does_not_shift_returns():
    # AAA skips day 2. with tail truncation its returns would pair with BBB's
    # returns one day off; aligned by date they stay matched.
    aaa = [100.0, 110.0, 121.0, 133.1, 146.41]  # +10% every day
    bbb = [100.0, 100.0, 100.0, 50.0, 50.0]  # only day 3 moves
    history = {"AAA": _bars("AAA", aaa, skip={2}), "BBB": _bars("BBB", bbb)}
    ctx = build_context(None, _positions("AAA", "BBB"), AS_OF, history, _bars("SPY", bbb))

    dates = [d for d in ctx.returns.index]
    assert len(dates) == 3  # day 2 dropped for both
    day3 = AS_OF - timedelta(days=1)
    # day 1 -> day 3 is a two-day span for both series
    assert ctx.returns.loc[day3, "AAA"] == pytest.approx(133.1 / 110.0 - 1.0)
    assert ctx.returns.loc[day3, "BBB"] == pytest.approx(-0.5)
    # and nothing else moved for BBB
    assert (ctx.returns["BBB"].drop(day3) == 0).all()


def test_aligned_prices_inner_joins_and_drops_empty():
    a = pd.Series([1.0, 2.0, 3.0], index=[1, 2, 3])
    b = pd.Series([5.0, 6.0], index=[2, 3])
    frame = aligned_prices({"A": a, "B": b, "C": pd.Series(dtype=float)})
    assert list(frame.columns) == ["A", "B"]
    assert list(frame.index) == [2, 3]


def test_ticker_without_history_keeps_its_weight_out_of_returns():
    closes = [100.0, 101.0, 102.0]
    history = {"AAA": _bars("AAA", closes), "ZZZ": []}
    ctx = build_context(None, _positions("AAA", "ZZZ"), AS_OF, history, _bars("SPY", closes))
    assert list(ctx.returns.columns) == ["AAA"]
    assert ctx.weights["ZZZ"] == pytest.approx(0.5)
    np.testing.assert_allclose(ctx.portfolio_returns, 0.5 * ctx.returns["AAA"])


def test_window_limits_returns_but_full_history_keeps_everything():
    closes = list(np.linspace(100, 200, 3000))
    history = {"AAA": _bars("AAA", closes)}
    ctx = build_context(None, _positions("AAA"), AS_OF, history, _bars("SPY", closes))
    start = window_start(AS_OF, 5)
    assert ctx.prices.index.min() >= start
    assert len(ctx.full_history["AAA"]) == 3000
    assert len(ctx.full_history["SPY"]) == 3000


def _ctx():
    closes = [100.0, 101.0, 99.0, 102.0]
    history = {"AAA": _bars("AAA", closes)}
    return build_context(None, _positions("AAA"), AS_OF, history, _bars("SPY", closes))


def test_failing_analyzer_only_errors_its_own_keys():
    def boom(ctx):
        raise ValueError("bad input")

    registry = [
        Analyzer("ok", ("a",), lambda ctx: {"a": 1}),
        Analyzer("boom", ("b", "c"), boom),
        Analyzer("after", ("d",), lambda ctx: {"d": ctx.results["a"] + 1}),
    ]
    out = run_analyzers(_ctx(), registry)
    assert out == {"a": 1, "b": {"error": "bad input"}, "c": {"error": "bad input"}, "d": 2}


def test_analyzer_missing_a_declared_key_is_an_error():
    out = run_analyzers(_ctx(), [Analyzer("partial", ("x", "y"), lambda ctx: {"x": 1})])
    assert out["x"]["error"].startswith("partial did not return")
    assert "error" in out["y"]


def test_registry_keys_are_unique():
    keys = [k for a in REGISTRY for k in a.keys]
    assert len(keys) == len(set(keys))
