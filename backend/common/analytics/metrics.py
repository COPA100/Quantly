import numpy as np

# trading days in a year, used to annualize daily statistics
TRADING_DAYS = 252


def annualized_volatility(returns, periods_per_year: int = TRADING_DAYS) -> float:
    # sample std of periodic returns scaled up to a yearly figure
    returns = np.asarray(returns, dtype=float)
    if returns.size < 2:
        return 0.0
    return float(np.std(returns, ddof=1) * np.sqrt(periods_per_year))
