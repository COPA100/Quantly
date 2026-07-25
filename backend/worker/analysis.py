import io
import math
from datetime import date
from typing import Any

import numpy as np

from common.analytics import basic, insights, metrics
from common.analytics.returns import daily_returns
from common.csv_reader import parse_portfolio
from common.market_data import ensure_benchmark, ensure_history, get_current_prices
from common.models import Portfolio, Price
from common.storage import get_storage
from worker.cache import get_cached, holdings_digest, set_cached


def _adj_closes(prices: list[Price]) -> np.ndarray:
    # adjusted close where present, raw close otherwise
    return np.array(
        [p.adj_close if p.adj_close is not None else p.close for p in prices], dtype=float
    )


def _weighted_returns(
    positions: list[dict], returns_by_ticker: dict[str, np.ndarray], total: float
) -> np.ndarray:
    # portfolio daily returns = value-weighted sum of the holdings' returns,
    # aligned on the most recent overlapping window
    if total <= 0:
        return np.empty(0)

    weights: dict[str, float] = {}
    for p in positions:
        symbol = str(p["symbol"]).upper()
        value = p["quantity"] * p["current_price"]
        weights[symbol] = weights.get(symbol, 0.0) + value / total

    series = [(t, r) for t, r in returns_by_ticker.items() if r.size > 0]
    if not series:
        return np.empty(0)

    n = min(r.size for _, r in series)
    aligned = np.zeros(n)
    for ticker, r in series:
        aligned += weights.get(ticker, 0.0) * r[-n:]
    return aligned


def _json_safe(value: Any) -> Any:
    # nan/inf (e.g. corr of a flat series) are not valid json / jsonb
    if isinstance(value, float):
        return value if math.isfinite(value) else 0.0
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def compute_analytics(db, portfolio: Portfolio, as_of: date | None = None) -> dict[str, Any]:
    # download the raw csv, value it at current prices, and compute the full
    # metric set from the shared price history. returns metric_name -> value.
    as_of = as_of or date.today()

    raw = get_storage().download_bytes(portfolio.s3_key)
    positions = parse_portfolio(io.BytesIO(raw))
    tickers = [str(p["symbol"]).upper() for p in positions]

    # identical book on the same day -> reuse the cached metrics, skip the
    # market-data fetch and the whole computation below
    digest = holdings_digest(positions, as_of)
    cached = get_cached(digest)
    if cached is not None:
        return cached

    # current prices value the book; a missing quote falls back to cost
    current = get_current_prices(tickers)
    for p in positions:
        p["current_price"] = current.get(str(p["symbol"]).upper(), p["purchase_price"])

    total = basic.calculate_portfolio_total(positions)
    gain_loss = basic.calculate_portfolio_gainloss(positions)
    basic.calculate_position_allocation(positions)
    allocation = [
        {"ticker": str(p["symbol"]).upper(), "pct_allocation": p.get("pct_allocation", 0.0)}
        for p in positions
    ]

    # per-ticker daily returns from the shared price table
    returns_by_ticker: dict[str, np.ndarray] = {}
    for ticker in dict.fromkeys(tickers):  # dedupe, preserve order
        history = ensure_history(db, ticker, as_of=as_of)
        returns_by_ticker[ticker] = daily_returns(_adj_closes(history))

    portfolio_returns = _weighted_returns(positions, returns_by_ticker, total)
    bench_returns = daily_returns(_adj_closes(ensure_benchmark(db, as_of=as_of)))

    corr = metrics.correlation_matrix(returns_by_ticker)
    avg_corr = metrics.average_correlation(corr["matrix"])
    vol = metrics.annualized_volatility(portfolio_returns)
    sharpe = metrics.sharpe_ratio(portfolio_returns)
    sortino = metrics.sortino_ratio(portfolio_returns)
    drawdown = metrics.max_drawdown(portfolio_returns)
    beta = metrics.beta(portfolio_returns, bench_returns)

    weights_sorted = sorted((p.get("pct_allocation", 0.0) for p in positions), reverse=True)
    top_n = min(3, len(weights_sorted))
    top_weight = sum(weights_sorted[:top_n])

    results = {
        "value": {"total": round(total, 2)},
        "gain_loss": gain_loss,
        "allocation": {"positions": allocation},
        "volatility": {"annualized": vol},
        "returns": {"annualized": metrics.annualized_return(portfolio_returns)},
        "sharpe": {"ratio": sharpe},
        "sortino": {"ratio": sortino},
        "drawdown": drawdown,
        "beta": {"beta": beta},
        "correlation": {"tickers": corr["tickers"], "matrix": corr["matrix"], "average": avg_corr},
        "insights": {
            "volatility": insights.volatility_insight(vol),
            "drawdown": insights.drawdown_insight(drawdown["max_drawdown"]),
            "sharpe": insights.sharpe_insight(sharpe),
            "sortino": insights.sortino_insight(sortino),
            "beta": insights.beta_insight(beta),
            "correlation": insights.correlation_insight(len(returns_by_ticker), avg_corr),
            "concentration": insights.concentration_insight(top_weight, top_n),
        },
    }
    results = _json_safe(results)
    set_cached(digest, results)
    return results
