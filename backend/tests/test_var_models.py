from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from common.analytics.analyzers import REGISTRY, run_analyzers
from common.analytics.analyzers.var import var as var_analyzer
from common.analytics.var_models import (
    backtest_var,
    christoffersen_independence,
    cornish_fisher_var_es,
    historical_var_es,
    horizon_returns,
    kupiec_pof,
    parametric_var_es,
)
from common.models import Price
from worker.analysis import build_context

AS_OF = date(2026, 6, 30)


def _normal(n=200_000, mu=0.0005, sigma=0.01, seed=1):
    return np.random.default_rng(seed).normal(mu, sigma, n)


def _series(r):
    return pd.Series(r, index=pd.date_range("2020-01-01", periods=len(r)).date)


@pytest.mark.parametrize("conf", [0.95, 0.99])
def test_methods_converge_on_large_normal_sample(conf):
    r = _normal()
    hist = historical_var_es(r, conf)
    para = parametric_var_es(r, conf)
    cf = cornish_fisher_var_es(r, conf)
    for a, b in ((hist, para), (cf, para)):
        assert a[0] == pytest.approx(b[0], rel=0.03)
        assert a[1] == pytest.approx(b[1], rel=0.03)


@pytest.mark.parametrize("fn", [historical_var_es, parametric_var_es, cornish_fisher_var_es])
def test_es_is_at_least_var(fn):
    r = np.random.default_rng(3).standard_t(4, 3000) * 0.01
    for conf in (0.95, 0.99):
        var, es = fn(r, conf)
        assert var > 0 and es >= var


def test_cornish_fisher_widens_for_fat_tails():
    r = np.random.default_rng(4).standard_t(3, 50_000) * 0.01
    assert cornish_fisher_var_es(r, 0.99)[0] > parametric_var_es(r, 0.99)[0]


def test_horizon_returns_compound_overlapping():
    out = horizon_returns(np.array([0.1, 0.1, -0.1, 0.0]), 2)
    assert out == pytest.approx([1.1 * 1.1 - 1, 1.1 * 0.9 - 1, 0.9 - 1])


def test_historical_hand_value():
    r = np.arange(-50, 50) / 1000.0
    var, es = historical_var_es(r, 0.95)
    assert var == pytest.approx(-np.quantile(r, 0.05))
    assert es == pytest.approx(-r[r <= np.quantile(r, 0.05)].mean())


def test_kupiec_matches_hand_computation():
    # 10 breaches in 100 days at p=0.05
    n, x, p = 100, 10, 0.05
    ll0 = (n - x) * np.log(1 - p) + x * np.log(p)
    ll1 = (n - x) * np.log(0.9) + x * np.log(0.1)
    lr, pv = kupiec_pof(n, x, p)
    assert lr == pytest.approx(-2 * (ll0 - ll1))
    assert lr == pytest.approx(4.13, abs=0.01)
    assert pv == pytest.approx(stats.chi2.sf(lr, 1))


def test_kupiec_edge_cases_are_finite():
    lr0, p0 = kupiec_pof(100, 0, 0.05)
    assert lr0 == pytest.approx(-2 * 100 * np.log(0.95))
    assert 0 <= p0 <= 1
    lr_all, p_all = kupiec_pof(100, 100, 0.05)
    assert lr_all == pytest.approx(-2 * 100 * np.log(0.05))
    assert np.isfinite(p_all)
    lr_ok, p_ok = kupiec_pof(100, 5, 0.05)
    assert lr_ok == pytest.approx(0.0, abs=1e-9) and p_ok == pytest.approx(1.0)


def test_christoffersen_known_sequence():
    # 0 1 0 0 1 1 0 0 0 1 -> transitions 00:3 01:3 10:2 11:1
    hits = np.array([0, 1, 0, 0, 1, 1, 0, 0, 0, 1])
    n00, n01, n10, n11 = 3, 3, 2, 1
    pi01, pi11, pi = 3 / 6, 1 / 3, 4 / 9

    def ll(a, b, q):
        return a * np.log(1 - q) + b * np.log(q)

    expected = -2 * (ll(n00 + n10, n01 + n11, pi) - ll(n00, n01, pi01) - ll(n10, n11, pi11))
    lr, pv = christoffersen_independence(hits)
    assert lr == pytest.approx(expected)
    assert pv == pytest.approx(stats.chi2.sf(expected, 1))


def test_christoffersen_edge_cases_are_finite():
    for hits in (np.zeros(50), np.ones(50), np.array([1]), np.array([], dtype=int)):
        lr, pv = christoffersen_independence(hits)
        assert lr == 0.0 and pv == 1.0
    clustered = np.zeros(200)
    clustered[50:60] = 1
    clustered[120:130] = 1
    lr, pv = christoffersen_independence(clustered)
    assert pv < 0.01


def test_backtest_iid_normal_shape():
    bt = backtest_var(_series(_normal(900, seed=7)))
    assert bt["n"] == 504
    assert len(bt["dates"]) == len(bt["returns"]) == len(bt["var"]) == 504
    assert bt["expected"] == pytest.approx(25.2)
    assert bt["exceptions"] == len(bt["exception_indices"])
    assert all(bt["returns"][i] < -bt["var"][i] for i in bt["exception_indices"])
    assert bt["kupiec"]["p"] > 0.01
    assert bt["verdict"]


def test_backtest_short_history_returns_none():
    assert backtest_var(_series(_normal(300))) is None


def test_backtest_flags_underestimated_risk():
    # calm year then a volatile stretch, so breaches pile up
    r = np.concatenate([_normal(250, 0, 0.002, 1), _normal(150, 0, 0.03, 2)])
    bt = backtest_var(_series(r))
    assert bt["exceptions"] > bt["expected"]
    assert bt["kupiec"]["p"] < 0.05
    assert "underestimated" in bt["verdict"]


def _ctx(n=900):
    rng = np.random.default_rng(5)
    closes = list(100 * np.cumprod(1 + rng.normal(0.0004, 0.01, n)))
    start = AS_OF - timedelta(days=n - 1)

    def bars(t):
        return [
            Price(ticker=t, date=start + timedelta(days=i), close=c, adj_close=c)
            for i, c in enumerate(closes)
        ]

    pos = [{"symbol": "AAA", "quantity": 1.0, "purchase_price": 100.0, "current_price": 100.0}]
    return build_context(None, pos, AS_OF, {"AAA": bars("AAA")}, bars("SPY"))


def _suite(ctx):
    return run_analyzers(ctx, [a for a in REGISTRY if a.name == "var_suite"])["var_suite"]


def test_analyzer_registered_after_insights_and_var_untouched():
    names = [a.name for a in REGISTRY]
    assert names.index("var_suite") > names.index("insights")
    ctx = _ctx()
    before = var_analyzer.fn(ctx)
    out = run_analyzers(ctx, [a for a in REGISTRY if a.name in ("var", "var_suite")])
    assert out["var"] == before["var"]


def test_analyzer_output_shape_and_determinism():
    out1, out2 = _suite(_ctx()), _suite(_ctx())
    assert out1 == out2
    for h in ("1d", "21d"):
        for c in ("0.95", "0.99"):
            cell = out1["methods"][h][c]
            assert set(cell) == {"historical", "parametric", "cornish_fisher", "monte_carlo"}
            for m in cell.values():
                assert m["es"] >= m["var"] >= 0
    assert out1["backtest"]["n"] > 0
    assert isinstance(out1["insight"], str)


def test_analyzer_short_history_omits_backtest_with_reason():
    out = _suite(_ctx(120))
    assert out["backtest"] is None and out["backtest_reason"]
    assert "1d" in out["methods"]
