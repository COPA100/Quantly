import numpy as np

# trading days in a year, used to annualize daily statistics
TRADING_DAYS = 252


def annualized_volatility(returns, periods_per_year: int = TRADING_DAYS) -> float:
    # sample std of periodic returns scaled up to a yearly figure
    returns = np.asarray(returns, dtype=float)
    if returns.size < 2:
        return 0.0
    return float(np.std(returns, ddof=1) * np.sqrt(periods_per_year))


def annualized_return(returns, periods_per_year: int = TRADING_DAYS) -> float:
    # geometric (compounded) growth rate, i.e. cagr of the return series
    returns = np.asarray(returns, dtype=float)
    if returns.size == 0:
        return 0.0
    cumulative = float(np.prod(1.0 + returns))
    if cumulative <= 0:
        return -1.0  # the position was wiped out
    return cumulative ** (periods_per_year / returns.size) - 1.0


def sharpe_ratio(
    returns, risk_free_rate: float = 0.0, periods_per_year: int = TRADING_DAYS
) -> float:
    # annualized excess return per unit of total volatility
    returns = np.asarray(returns, dtype=float)
    if returns.size < 2:
        return 0.0
    excess = returns - risk_free_rate / periods_per_year
    std = np.std(excess, ddof=1)
    # tolerance, not == 0: a constant series has std ~1e-18 from rounding
    if std < 1e-12:
        return 0.0
    return float(np.mean(excess) / std * np.sqrt(periods_per_year))


def sortino_ratio(
    returns, risk_free_rate: float = 0.0, periods_per_year: int = TRADING_DAYS
) -> float:
    # like sharpe but only downside volatility is penalized
    returns = np.asarray(returns, dtype=float)
    if returns.size < 2:
        return 0.0
    excess = returns - risk_free_rate / periods_per_year
    downside = np.minimum(excess, 0.0)
    downside_dev = np.sqrt(np.mean(downside**2))
    if downside_dev < 1e-12:
        return 0.0  # nothing below target, ratio is undefined
    return float(np.mean(excess) / downside_dev * np.sqrt(periods_per_year))


def max_drawdown(returns) -> dict:
    # worst peak-to-trough decline and the longest time spent below a prior peak
    returns = np.asarray(returns, dtype=float)
    if returns.size == 0:
        return {"max_drawdown": 0.0, "duration": 0}

    # start the equity curve at 1.0 so a decline from day one is counted
    equity = np.concatenate([[1.0], np.cumprod(1.0 + returns)])
    running_max = np.maximum.accumulate(equity)
    drawdowns = equity / running_max - 1.0

    longest = current = 0
    for underwater in drawdowns < 0:
        current = current + 1 if underwater else 0
        longest = max(longest, current)

    return {"max_drawdown": float(drawdowns.min()), "duration": int(longest)}
