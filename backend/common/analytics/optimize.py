"""covariance estimation and long-only portfolio optimizers for the efficient frontier.

everything here takes plain numpy arrays. covariances passed to the optimizers
are in whatever units the caller likes (the frontier analyzer uses annual).
"""

import numpy as np
from scipy.optimize import minimize

MAX_WEIGHT = 0.40


def ledoit_wolf_cov(x: np.ndarray) -> tuple[np.ndarray, float]:
    """shrunk covariance of a (rows x assets) matrix and the shrinkage intensity.

    the Ledoit-Wolf (2004) estimator with the scaled-identity target: the sample
    covariance S is blended with mu*I, mu = trace(S)/n, by the intensity that
    minimizes expected squared error. frobenius norms are divided by n, as in
    the paper. with few rows per asset the sample covariance is noisy and the
    optimizer would chase that noise, shrinking keeps it well conditioned.
    """
    t, n = x.shape
    xc = x - x.mean(axis=0)
    s = xc.T @ xc / t
    mu = np.trace(s) / n
    # d2: dispersion of S around the target, b2: estimation error of S
    d2 = np.sum((s - mu * np.eye(n)) ** 2) / n
    if d2 <= 0:
        return s, 0.0
    sq = xc**2
    b2 = (np.sum(sq.T @ sq) / t - np.sum(s**2)) / (t * n)
    b2 = min(b2, d2)
    shrink = float(b2 / d2)
    return shrink * mu * np.eye(n) + (1 - shrink) * s, shrink


def shrunk_mean_returns(x: np.ndarray) -> np.ndarray:
    """sample mean returns pulled toward the cross-sectional mean, James-Stein style.

    sample means over a few years are mostly noise, and an optimizer loads up on
    whichever asset got lucky. shrinking each mean toward the group mean cuts
    that estimation error. the factor is 1 - (n-3)*s2/sum((m-grand)^2) floored
    at 0, with s2 the average variance of a sample mean. n <= 3 gets no shrink.
    """
    t, n = x.shape
    m = x.mean(axis=0)
    grand = m.mean()
    spread = float(np.sum((m - grand) ** 2))
    if n <= 3 or spread == 0:
        return m
    s2 = float(np.mean(x.var(axis=0, ddof=1))) / t
    keep = max(0.0, 1.0 - (n - 3) * s2 / spread)
    return grand + keep * (m - grand)


def weight_cap(n: int) -> float:
    # a 40% cap needs at least 3 assets to sum to 1, with fewer it is dropped
    return MAX_WEIGHT if n * MAX_WEIGHT >= 1 else 1.0


def _solve(fun, x0, cap, constraints=None, jac=None) -> np.ndarray:
    n = len(x0)
    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1.0, "jac": lambda w: np.ones(n)}]
    cons += constraints or []
    res = minimize(
        fun,
        x0,
        jac=jac,
        bounds=[(0.0, cap)] * n,
        constraints=cons,
        method="SLSQP",
        options={"maxiter": 500, "ftol": 1e-14},
    )
    w = np.clip(res.x, 0.0, cap)
    return w / w.sum()


def _start(n: int) -> np.ndarray:
    return np.full(n, 1.0 / n)


def min_variance(cov: np.ndarray, cap: float) -> np.ndarray:
    n = len(cov)
    return _solve(lambda w: w @ cov @ w, _start(n), cap, jac=lambda w: 2 * cov @ w)


def max_return(mu: np.ndarray, cap: float) -> np.ndarray:
    # lp solution: fill the best assets up to the cap in order
    w = np.zeros(len(mu))
    left = 1.0
    for i in np.argsort(-mu, kind="stable"):
        w[i] = min(cap, left)
        left -= w[i]
    return w


def efficient_frontier(
    mu: np.ndarray, cov: np.ndarray, cap: float, n_points: int
) -> list[tuple[float, float, np.ndarray]]:
    """(vol, return, weights) at evenly spaced target returns, min variance to max return."""
    lo = min_variance(cov, cap)
    hi = max_return(mu, cap)
    targets = np.linspace(float(mu @ lo), float(mu @ hi), n_points)
    out = []
    w = lo
    for target in targets:
        cons = [{"type": "eq", "fun": lambda w, t=target: mu @ w - t, "jac": lambda w: mu}]
        w = _solve(lambda w: w @ cov @ w, w, cap, cons, jac=lambda w: 2 * cov @ w)
        out.append((float(np.sqrt(w @ cov @ w)), float(mu @ w), w))
    return out


def max_sharpe(mu: np.ndarray, cov: np.ndarray, cap: float, rf: float = 0.0) -> np.ndarray:
    def neg_sharpe(w):
        return -(mu @ w - rf) / np.sqrt(max(w @ cov @ w, 1e-18))

    n = len(mu)
    best, best_val = None, np.inf
    # a couple of starts, the ratio is not convex
    for x0 in (_start(n), min_variance(cov, cap), max_return(mu, cap)):
        w = _solve(neg_sharpe, x0, cap)
        val = neg_sharpe(w)
        if val < best_val - 1e-12:
            best, best_val = w, val
    return best


def risk_parity(cov: np.ndarray, cap: float) -> np.ndarray:
    """equal risk contributions. spinu's convex form, then a capped solve if it breaks the cap.

    minimize 0.5 y'Sy - (1/n) sum(log y) over y > 0, the weights are y / sum(y).
    """
    n = len(cov)
    res = minimize(
        lambda y: 0.5 * y @ cov @ y - np.log(y).sum() / n,
        np.full(n, 1.0 / n),
        jac=lambda y: cov @ y - 1.0 / (n * y),
        bounds=[(1e-10, None)] * n,
        method="L-BFGS-B",
        options={"maxiter": 1000, "ftol": 1e-15, "gtol": 1e-12},
    )
    w = res.x / res.x.sum()
    if w.max() <= cap + 1e-9:
        return w

    def spread(w):
        rc = w * (cov @ w)
        return np.sum((rc / rc.sum() - 1.0 / n) ** 2)

    return _solve(spread, np.minimum(w, cap) / np.minimum(w, cap).sum(), cap)
