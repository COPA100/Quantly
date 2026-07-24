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
