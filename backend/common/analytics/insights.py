"""turn raw metrics into plain-english interpretations, the layer 2 product."""


def _pct(value: float, digits: int = 0) -> str:
    return f"{value * 100:.{digits}f}%"


def volatility_insight(annual_vol: float) -> str:
    return (
        f"Annualized volatility of {_pct(annual_vol)}. "
        "That is roughly how much the portfolio swings in a typical year."
    )


def drawdown_insight(max_drawdown: float) -> str:
    fall = _pct(abs(max_drawdown))
    return (
        f"Max drawdown of {_pct(max_drawdown)}. "
        f"In a rough stretch like 2022 you would have lost about {fall} of your value."
    )


def sharpe_insight(sharpe: float, benchmark_sharpe: float | None = None) -> str:
    if benchmark_sharpe is None:
        return f"Sharpe ratio of {sharpe:.2f}, your return per unit of risk taken."
    verdict = "less return for the risk" if sharpe < benchmark_sharpe else "a solid payoff"
    return (
        f"Sharpe {sharpe:.2f} vs the market's {benchmark_sharpe:.2f}. "
        f"You are getting {verdict} compared with just buying the index."
    )


def sortino_insight(sortino: float) -> str:
    return (
        f"Sortino ratio of {sortino:.2f}. "
        "Like Sharpe, but it only counts downside moves as risk."
    )


def beta_insight(beta: float) -> str:
    swing = abs(beta - 1.0)
    direction = "harder" if beta > 1.0 else "softer"
    return (
        f"Beta {beta:.2f}. You tend to move about {_pct(swing)} {direction} "
        "than the market, both up and down."
    )


def correlation_insight(n_holdings: int, avg_correlation: float) -> str:
    if avg_correlation >= 0.7:
        meaning = "You effectively own one bet, not many"
    elif avg_correlation >= 0.4:
        meaning = "You have some diversification, but the names move together"
    else:
        meaning = "The holdings are fairly independent, which is real diversification"
    return f"{n_holdings} holdings at {avg_correlation:.2f} average correlation. {meaning}."


def concentration_insight(top_weight: float, top_n: int) -> str:
    return f"{_pct(top_weight)} of your money is in your top {top_n} positions."
