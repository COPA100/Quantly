"""value at risk estimators and backtests. pure functions over return arrays.

every var and es is a positive loss as a fraction of portfolio value, floored
at zero, and es >= var always.
"""

from typing import Any

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view
from scipy import stats
from scipy.special import xlogy

BACKTEST_WINDOW = 250
BACKTEST_DAYS = 504
BACKTEST_MIN_DAYS = 100
BACKTEST_CONFIDENCE = 0.95
SIGNIFICANCE = 0.05
_ES_GRID = 2000


def horizon_returns(returns: np.ndarray, horizon: int) -> np.ndarray:
    # overlapping h-day compounded returns, one per start day
    if horizon <= 1:
        return np.asarray(returns, dtype=float)
    growth = sliding_window_view(1.0 + np.asarray(returns, dtype=float), horizon)
    return growth.prod(axis=1) - 1.0


def historical_var_es(returns: np.ndarray, confidence: float) -> tuple[float, float]:
    # empirical quantile, es is the mean of the observations at or beyond it
    q = float(np.quantile(returns, 1.0 - confidence))
    tail = returns[returns <= q]
    return max(-q, 0.0), max(-float(tail.mean()), 0.0)


def _moments(returns: np.ndarray, horizon: int) -> tuple[float, float, float, float]:
    # daily moments scaled to the horizon: mean x h, std x sqrt(h) (iid assumption),
    # skew / sqrt(h) and excess kurtosis / h (what summing h iid days does)
    mu = float(np.mean(returns))
    sigma = float(np.std(returns, ddof=1))
    skew = float(stats.skew(returns))
    kurt = float(stats.kurtosis(returns))
    return mu * horizon, sigma * np.sqrt(horizon), skew / np.sqrt(horizon), kurt / horizon


def parametric_var_es(
    returns: np.ndarray, confidence: float, horizon: int = 1
) -> tuple[float, float]:
    # normal returns, scaled to the horizon by sqrt-time
    mu, sigma, _, _ = _moments(returns, horizon)
    alpha = 1.0 - confidence
    z = stats.norm.ppf(alpha)
    var = -(mu + z * sigma)
    es = -(mu - sigma * stats.norm.pdf(z) / alpha)
    return max(var, 0.0), max(es, var, 0.0)


def _cf_z(z: np.ndarray | float, skew: float, kurt: float) -> np.ndarray | float:
    # cornish-fisher expansion of the normal quantile (excess kurtosis)
    return (
        z
        + (z**2 - 1.0) * skew / 6.0
        + (z**3 - 3.0 * z) * kurt / 24.0
        - (2.0 * z**3 - 5.0 * z) * skew**2 / 36.0
    )


def cornish_fisher_var_es(
    returns: np.ndarray, confidence: float, horizon: int = 1
) -> tuple[float, float]:
    # normal quantile adjusted for sample skew and excess kurtosis. es averages
    # the adjusted quantile over the tail probabilities on a midpoint grid.
    mu, sigma, skew, kurt = _moments(returns, horizon)
    alpha = 1.0 - confidence
    var = -(mu + _cf_z(stats.norm.ppf(alpha), skew, kurt) * sigma)
    u = (np.arange(_ES_GRID) + 0.5) / _ES_GRID * alpha
    es = -float(np.mean(mu + _cf_z(stats.norm.ppf(u), skew, kurt) * sigma))
    return max(var, 0.0), max(es, var, 0.0)


def _log_lik(n_ok: float, n_hit: float, p: float) -> float:
    # bernoulli log likelihood, with 0 * log(0) = 0 so edge cases stay finite
    return float(xlogy(n_ok, 1.0 - p) + xlogy(n_hit, p))


def kupiec_pof(n: int, exceptions: int, p: float) -> tuple[float, float]:
    # proportion-of-failures test: observed breach rate vs p, chi2 with 1 df.
    # zero or all breaches are fine, the 0 * log(0) terms drop out.
    if n <= 0:
        return 0.0, 1.0
    rate = exceptions / n
    lr = -2.0 * (
        _log_lik(n - exceptions, exceptions, p) - _log_lik(n - exceptions, exceptions, rate)
    )
    lr = max(lr, 0.0)
    return lr, float(stats.chi2.sf(lr, 1))


def christoffersen_independence(hits: np.ndarray) -> tuple[float, float]:
    # tests whether a breach today changes the chance of one tomorrow, from the
    # 2x2 transition counts. convention: with no transitions to compare (fewer
    # than 2 days, no breaches, or no non-breaches) the test is uninformative and
    # returns lr 0, p 1.
    h = np.asarray(hits, dtype=int)
    if h.size < 2:
        return 0.0, 1.0
    prev, cur = h[:-1], h[1:]
    n00 = float(np.sum((prev == 0) & (cur == 0)))
    n01 = float(np.sum((prev == 0) & (cur == 1)))
    n10 = float(np.sum((prev == 1) & (cur == 0)))
    n11 = float(np.sum((prev == 1) & (cur == 1)))
    total = n00 + n01 + n10 + n11
    if n01 + n11 == 0 or n00 + n10 == 0:
        return 0.0, 1.0
    pi = (n01 + n11) / total
    pi01 = n01 / (n00 + n01) if n00 + n01 else 0.0
    pi11 = n11 / (n10 + n11) if n10 + n11 else 0.0
    lr = -2.0 * (
        _log_lik(n00 + n10, n01 + n11, pi) - _log_lik(n00, n01, pi01) - _log_lik(n10, n11, pi11)
    )
    lr = max(lr, 0.0)
    return lr, float(stats.chi2.sf(lr, 1))


def _verdict(n: int, x: int, expected: float, p_kupiec: float, p_chris: float) -> str:
    counts = f"{x} breaches vs {expected:.0f} expected (p={p_kupiec:.2f})"
    if p_kupiec < SIGNIFICANCE:
        if x > expected:
            text = f"VaR underestimated risk: {counts}."
        else:
            text = f"VaR was too conservative: {counts}."
    else:
        text = f"VaR was well calibrated: {counts}."
    if p_chris < SIGNIFICANCE:
        text += (
            f" Breaches clustered in time (p={p_chris:.2f}), "
            "so the model reacts slowly to volatile spells."
        )
    else:
        text += f" Breaches were not clustered (p={p_chris:.2f})."
    return text


def backtest_var(portfolio_returns: pd.Series) -> dict[str, Any] | None:
    # 1-day 95% historical VaR from the prior 250 days, scored against each of
    # the last 504 days. a breach is a return below -var. None when there are
    # fewer than 100 test days.
    r = portfolio_returns.to_numpy(dtype=float)
    n_test = min(BACKTEST_DAYS, r.size - BACKTEST_WINDOW)
    if n_test < BACKTEST_MIN_DAYS:
        return None
    first = r.size - n_test
    windows = sliding_window_view(r, BACKTEST_WINDOW)[
        first - BACKTEST_WINDOW : first - BACKTEST_WINDOW + n_test
    ]
    var = np.maximum(-np.quantile(windows, 1.0 - BACKTEST_CONFIDENCE, axis=1), 0.0)
    realized = r[first:]
    hits = realized < -var
    x = int(hits.sum())
    p = 1.0 - BACKTEST_CONFIDENCE
    expected = p * n_test
    lr_k, p_k = kupiec_pof(n_test, x, p)
    lr_c, p_c = christoffersen_independence(hits.astype(int))
    return {
        "dates": [str(d) for d in portfolio_returns.index[first:]],
        "returns": realized.tolist(),
        "var": var.tolist(),
        "exception_indices": np.flatnonzero(hits).tolist(),
        "n": n_test,
        "exceptions": x,
        "expected": expected,
        "kupiec": {"lr": lr_k, "p": p_k},
        "christoffersen": {"lr": lr_c, "p": p_c},
        "verdict": _verdict(n_test, x, expected, p_k, p_c),
    }
