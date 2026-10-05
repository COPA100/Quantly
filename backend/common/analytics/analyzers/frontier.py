from typing import Any

import numpy as np

from common.analytics import optimize
from common.analytics.analyzers.base import analyzer
from common.analytics.context import AnalysisContext

TRADING_DAYS = 252
N_POINTS = 30
MIN_ROWS = 30
# gains under this (0.1 points a year) count as already on the frontier
NEGLIGIBLE_GAIN = 0.001


def _empty(insight: str) -> dict[str, Any]:
    return {
        "frontier": {
            "points": [],
            "current": None,
            "min_variance": None,
            "max_sharpe": None,
            "risk_parity": None,
            "insight": insight,
        }
    }


def _portfolio(w: np.ndarray, tickers: list[str], mu: np.ndarray, cov: np.ndarray) -> dict:
    return {
        "vol": float(np.sqrt(w @ cov @ w)),
        "ret": float(mu @ w),
        "weights": {t: float(x) for t, x in zip(tickers, w, strict=True)},
    }


def _insight(current: dict, points: list[dict]) -> str:
    vols = np.maximum.accumulate([p["vol"] for p in points])
    rets = [p["ret"] for p in points]
    # best return the frontier offers at the current volatility
    best = float(np.interp(current["vol"], vols, rets))
    gain = best - current["ret"]
    caveat = (
        " This is in-sample: it is built from past returns, so treat it as a guide "
        "to diversification, not a forecast."
    )
    if gain <= NEGLIGIBLE_GAIN:
        return "Your mix already sits close to the efficient frontier for its risk." + caveat
    return (
        f"At your current risk, an in-sample optimal mix would have returned "
        f"{gain * 100:.1f}% more a year." + caveat
    )


@analyzer("frontier", keys=("frontier",))
def frontier(ctx: AnalysisContext) -> dict[str, Any]:
    # fixed ticker order: the optimizer only converges to a tolerance, so input
    # order would otherwise leak into the weights (and the cache is order free)
    returns = ctx.returns.dropna().sort_index(axis=1)
    tickers = list(returns.columns)
    if len(tickers) < 2:
        return _empty("The efficient frontier needs at least two holdings with price history.")
    if len(returns) < MIN_ROWS:
        return _empty(
            f"Not enough price history for an efficient frontier, "
            f"it needs about {MIN_ROWS} trading days."
        )

    x = returns.to_numpy()
    daily_cov, _ = optimize.ledoit_wolf_cov(x)
    cov = daily_cov * TRADING_DAYS
    # shrink toward capm-implied returns when the benchmark is there, so a fully
    # shrunk estimate still ranks assets by market exposure
    market = ctx.benchmark_returns.reindex(returns.index).dropna()
    if len(market) == len(returns):
        prior = optimize.capm_prior(x, market.to_numpy())
    else:
        prior = None
    mu = optimize.shrunk_mean_returns(x, prior) * TRADING_DAYS
    cap = optimize.weight_cap(len(tickers))

    held = ctx.weights.reindex(tickers).fillna(0.0).to_numpy()
    if held.sum() <= 0:
        return _empty("None of your holdings have price history, so there is no frontier.")
    current = _portfolio(held / held.sum(), tickers, mu, cov)

    curve = optimize.efficient_frontier(mu, cov, cap, N_POINTS)
    points = [{"vol": v, "ret": r} for v, r, _ in curve]
    return {
        "frontier": {
            "points": points,
            "current": current,
            "min_variance": _portfolio(optimize.min_variance(cov, cap), tickers, mu, cov),
            "max_sharpe": _portfolio(optimize.max_sharpe(mu, cov, cap), tickers, mu, cov),
            "risk_parity": _portfolio(optimize.risk_parity(cov, cap), tickers, mu, cov),
            "insight": _insight(current, points),
        }
    }
