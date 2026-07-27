"""Analytics backed by the C++ engine when installed, pure-python otherwise.

The worker imports these instead of calling the baselines directly, so the same
code path runs whether or not the compiled `engine` wheel is present. Only the
operations where C++ genuinely wins are routed here (path-dependent drawdown,
the correlation kernel, Monte Carlo VaR); the rest stay in numpy.
"""

import numpy as np

from common.analytics import metrics, risk

try:
    import engine as _engine
except ImportError:  # the wheel is optional; fall back to pure python
    _engine = None


def using_native() -> bool:
    return _engine is not None


def max_drawdown(returns) -> dict:
    if _engine is None:
        return metrics.max_drawdown(returns)
    return _engine.max_drawdown(np.asarray(returns, dtype=float))


def correlation_matrix(returns_by_ticker: dict) -> dict:
    # keep the python alignment + identity handling; only the corrcoef kernel
    # moves to c++ (and only when it would actually run)
    tickers = list(returns_by_ticker)
    series = [np.asarray(returns_by_ticker[t], dtype=float) for t in tickers]
    n = min((s.size for s in series), default=0)
    if _engine is None or len(tickers) < 2 or n < 2:
        return metrics.correlation_matrix(returns_by_ticker)

    stacked = np.ascontiguousarray(np.vstack([s[-n:] for s in series]))
    matrix = _engine.correlation_matrix(stacked)
    return {"tickers": tickers, "matrix": matrix.tolist()}


def monte_carlo_var(
    mu: float,
    sigma: float,
    horizon: int,
    n_sims: int,
    confidence: float = 0.95,
    seed: int = 0,
) -> dict:
    if _engine is None:
        return risk.monte_carlo_var(mu, sigma, horizon, n_sims, confidence, seed)
    return _engine.monte_carlo_var(mu, sigma, horizon, n_sims, confidence, seed)
