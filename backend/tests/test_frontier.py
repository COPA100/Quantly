from datetime import date

import numpy as np
import pandas as pd
import pytest

from common.analytics import optimize
from common.analytics.analyzers import REGISTRY, run_analyzers
from common.analytics.analyzers.frontier import frontier
from common.analytics.context import AnalysisContext


def _returns(n_assets: int = 4, rows: int = 400, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    market = rng.normal(0.0004, 0.01, rows)
    data = {}
    for i in range(n_assets):
        beta = 0.5 + 0.3 * i
        noise = rng.normal(0.0, 0.004 + 0.002 * i, rows)
        data[f"T{i}"] = 0.0002 * i + beta * market + noise
    idx = pd.bdate_range("2023-01-02", periods=rows)
    return pd.DataFrame(data, index=idx)


def _ctx(returns: pd.DataFrame, weights: dict[str, float] | None = None) -> AnalysisContext:
    w = pd.Series(weights or {c: 1 / returns.shape[1] for c in returns.columns}, dtype=float)
    port = returns.mul(w.reindex(returns.columns).fillna(0.0), axis=1).sum(axis=1)
    return AnalysisContext(
        as_of=date(2026, 6, 30),
        positions=[],
        total=1000.0,
        weights=w,
        prices=pd.DataFrame(),
        returns=returns,
        portfolio_returns=port,
        benchmark_returns=port,
        history={},
        full_history={},
        benchmark_ticker="SPY",
    )


def _cov_mu(returns: pd.DataFrame):
    cov, _ = optimize.ledoit_wolf_cov(returns.to_numpy())
    return cov * 252, optimize.shrunk_mean_returns(returns.to_numpy()) * 252


# ledoit-wolf


def _lw_reference(x: np.ndarray):
    # direct loop transcription of the 2004 identity-target formula
    t, n = x.shape
    xc = x - x.mean(axis=0)
    s = xc.T @ xc / t
    mu = np.trace(s) / n
    d2 = np.sum((s - mu * np.eye(n)) ** 2) / n
    b2 = 0.0
    for k in range(t):
        outer = np.outer(xc[k], xc[k])
        b2 += np.sum((outer - s) ** 2) / n
    b2 = min(b2 / t**2, d2)
    shrink = b2 / d2
    return shrink * mu * np.eye(n) + (1 - shrink) * s, shrink


def test_ledoit_wolf_matches_hand_computation():
    x = _returns(3, 60).to_numpy()
    cov, shrink = optimize.ledoit_wolf_cov(x)
    ref, ref_shrink = _lw_reference(x)
    assert shrink == pytest.approx(ref_shrink)
    assert cov == pytest.approx(ref)


def test_ledoit_wolf_properties():
    x = _returns(5, 40).to_numpy()
    sample = np.cov(x, rowvar=False, bias=True)
    cov, shrink = optimize.ledoit_wolf_cov(x)
    assert 0.0 <= shrink <= 1.0
    assert np.trace(cov) == pytest.approx(np.trace(sample))  # trace preserved
    assert np.allclose(cov, cov.T)
    assert np.linalg.eigvalsh(cov).min() > 0
    # shrinking toward the identity pulls the eigenvalue spread in
    eig_s, eig_c = np.linalg.eigvalsh(sample), np.linalg.eigvalsh(cov)
    assert eig_c.max() <= eig_s.max() and eig_c.min() >= eig_s.min()


def test_ledoit_wolf_shrinks_less_with_more_data():
    short = optimize.ledoit_wolf_cov(_returns(4, 40).to_numpy())[1]
    long = optimize.ledoit_wolf_cov(_returns(4, 2000).to_numpy())[1]
    assert long < short


def test_shrunk_means_pull_toward_cross_section():
    x = _returns(6, 120).to_numpy()
    raw, shrunk = x.mean(axis=0), optimize.shrunk_mean_returns(x)
    assert shrunk.mean() == pytest.approx(raw.mean())
    assert shrunk.std() < raw.std()


# optimizers


def test_weight_cap_is_feasible():
    assert optimize.weight_cap(2) == 1.0
    assert optimize.weight_cap(3) == 0.40
    assert optimize.weight_cap(10) == 0.40


def test_two_asset_min_variance_matches_closed_form():
    cov = np.array([[0.04, 0.006], [0.006, 0.01]])
    w = optimize.min_variance(cov, cap=1.0)
    closed = (cov[1, 1] - cov[0, 1]) / (cov[0, 0] + cov[1, 1] - 2 * cov[0, 1])
    assert w[0] == pytest.approx(closed, abs=1e-5)
    assert w.sum() == pytest.approx(1.0)


def test_portfolios_sum_to_one_and_respect_bounds():
    cov, mu = _cov_mu(_returns(6))
    cap = optimize.weight_cap(6)
    for w in (
        optimize.min_variance(cov, cap),
        optimize.max_sharpe(mu, cov, cap),
        optimize.risk_parity(cov, cap),
    ):
        assert w.sum() == pytest.approx(1.0, abs=1e-6)
        assert w.min() >= -1e-9
        assert w.max() <= cap + 1e-6


def test_min_variance_is_lowest_vol_on_frontier():
    cov, mu = _cov_mu(_returns(5))
    pts = optimize.efficient_frontier(mu, cov, optimize.weight_cap(5), 30)
    assert len(pts) == 30
    vols = [p[0] for p in pts]
    assert vols[0] == pytest.approx(min(vols), abs=1e-9)
    rets = [p[1] for p in pts]
    assert np.all(np.diff(rets) >= -1e-9)
    mv = optimize.min_variance(cov, optimize.weight_cap(5))
    assert vols[0] == pytest.approx(float(np.sqrt(mv @ cov @ mv)), abs=1e-6)


def test_risk_parity_contributions_equal():
    cov, _ = _cov_mu(_returns(5))
    w = optimize.risk_parity(cov, optimize.weight_cap(5))
    rc = w * (cov @ w)
    assert rc / rc.sum() == pytest.approx(np.full(5, 0.2), abs=1e-3)


def test_max_sharpe_beats_equal_weight():
    cov, mu = _cov_mu(_returns(5))
    w = optimize.max_sharpe(mu, cov, optimize.weight_cap(5))
    eq = np.full(5, 0.2)

    def sharpe(v):
        return (mu @ v) / np.sqrt(v @ cov @ v)

    assert sharpe(w) >= sharpe(eq) - 1e-9


# analyzer


def test_analyzer_output_shape():
    ctx = _ctx(_returns(4), {"T0": 0.4, "T1": 0.3, "T2": 0.2, "T3": 0.1})
    out = frontier.fn(ctx)["frontier"]
    assert len(out["points"]) == 30
    for key in ("current", "min_variance", "max_sharpe", "risk_parity"):
        assert out[key]["vol"] > 0
        assert set(out[key]["weights"]) == {"T0", "T1", "T2", "T3"}
        assert sum(out[key]["weights"].values()) == pytest.approx(1.0, abs=1e-6)
    assert out["current"]["weights"]["T0"] == pytest.approx(0.4)
    assert out["min_variance"]["vol"] <= out["current"]["vol"] + 1e-9
    assert "in-sample" in out["insight"]


def test_analyzer_is_deterministic():
    ctx = _ctx(_returns(4))
    assert frontier.fn(ctx) == frontier.fn(ctx)


def test_analyzer_ignores_tickers_without_returns():
    ctx = _ctx(_returns(3), {"T0": 0.4, "T1": 0.3, "T2": 0.2, "GHOST": 0.1})
    out = frontier.fn(ctx)["frontier"]
    assert "GHOST" not in out["current"]["weights"]
    assert sum(out["current"]["weights"].values()) == pytest.approx(1.0)


def test_single_ticker_is_degenerate():
    out = frontier.fn(_ctx(_returns(1)))["frontier"]
    assert out["points"] == []
    assert "two" in out["insight"]


def test_short_history_is_degenerate():
    out = frontier.fn(_ctx(_returns(3, rows=20)))["frontier"]
    assert out["points"] == []
    assert "history" in out["insight"]


def test_registered_and_runs_through_registry():
    assert frontier in REGISTRY
    results = run_analyzers(_ctx(_returns(3)), [frontier])
    assert len(results["frontier"]["points"]) == 30
