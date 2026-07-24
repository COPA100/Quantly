import numpy as np


def daily_returns(prices) -> np.ndarray:
    # simple period-over-period returns, length is len(prices) - 1
    prices = np.asarray(prices, dtype=float)
    if prices.size < 2:
        return np.empty(0)
    return prices[1:] / prices[:-1] - 1.0


def log_returns(prices) -> np.ndarray:
    # log returns, additive over time and used for most of the risk math
    prices = np.asarray(prices, dtype=float)
    if prices.size < 2:
        return np.empty(0)
    return np.log(prices[1:] / prices[:-1])
