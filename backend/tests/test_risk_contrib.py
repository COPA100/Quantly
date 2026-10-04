from datetime import date

import numpy as np
import pandas as pd
import pytest

from common.analytics.analyzers import risk_contrib as rc
from common.analytics.context import AnalysisContext


def make_ctx(returns: pd.DataFrame, weights: dict[str, float]) -> AnalysisContext:
    return AnalysisContext(
        as_of=date(2026, 6, 30),
        positions=[],
        total=1.0,
        weights=pd.Series(weights, dtype=float),
        prices=pd.DataFrame(),
        returns=returns,
        portfolio_returns=pd.Series(dtype=float),
        benchmark_returns=pd.Series(dtype=float),
        history={},
        full_history={},
        benchmark_ticker="SPY",
    )


def test_euler_contributions_sum_to_portfolio_sigma():
    rng = np.random.default_rng(7)
    a = rng.normal(size=(200, 4)) @ np.diag([1, 2, 3, 4.0])
    cov = np.cov(a, rowvar=False) + 0.5
    w = np.array([0.4, 0.3, 0.2, 0.1])
    sigma, parts = rc.euler_decomposition(w, cov)
    assert sigma == pytest.approx(float(np.sqrt(w @ cov @ w)), rel=1e-14)
    assert parts.sum() == pytest.approx(sigma, rel=1e-12)


def test_identical_uncorrelated_assets_contribute_equally():
    rng = np.random.default_rng(3)
    # orthonormal columns: sample correlations are exactly zero, variances equal
    raw = rng.normal(size=(500, 3))
    raw -= raw.mean(axis=0)
    q, _ = np.linalg.qr(raw)
    returns = pd.DataFrame(q * 0.01 * np.sqrt(499), columns=["A", "B", "C"])
    out = rc.risk_contribution.fn(make_ctx(returns, {"A": 1, "B": 1, "C": 1}))["risk_contribution"]
    shares = [h["pct_risk"] for h in out["holdings"]]
    assert shares == pytest.approx([1 / 3] * 3, abs=1e-9)


def test_analyzer_output_sums_and_renormalizes_weights():
    rng = np.random.default_rng(11)
    returns = pd.DataFrame(rng.normal(0, 0.01, size=(300, 3)), columns=["A", "B", "C"])
    # weights over priced tickers only sum to 0.6, and Z has no returns
    weights = {"A": 0.3, "B": 0.2, "C": 0.1, "Z": 0.4}
    out = rc.risk_contribution.fn(make_ctx(returns, weights))["risk_contribution"]
    holdings = out["holdings"]
    assert sum(h["weight"] for h in holdings) == pytest.approx(1.0)
    assert sum(h["pct_risk"] for h in holdings) == pytest.approx(1.0)
    w = np.array([0.5, 1 / 3, 1 / 6])
    sigma = float(np.sqrt(w @ (np.cov(returns.to_numpy(), rowvar=False) * 252) @ w))
    assert sum(h["rc"] for h in holdings) == pytest.approx(sigma)
    shares = [h["pct_risk"] for h in holdings]
    assert shares == sorted(shares, reverse=True)


def test_insight_names_the_risk_heavy_holding():
    rng = np.random.default_rng(5)
    returns = pd.DataFrame(
        {"AAPL": rng.normal(0, 0.03, size=400), "BND": rng.normal(0, 0.005, size=400)}
    )
    out = rc.risk_contribution.fn(make_ctx(returns, {"AAPL": 0.2, "BND": 0.8}))["risk_contribution"]
    assert out["insight"].startswith("AAPL is 20% of your money but ")
    assert out["holdings"][0]["marginal_var"] > out["holdings"][1]["marginal_var"]


def test_no_returns_gives_empty_holdings():
    out = rc.risk_contribution.fn(make_ctx(pd.DataFrame(), {"A": 1.0}))["risk_contribution"]
    assert out["holdings"] == []
