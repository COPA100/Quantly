import io
import math
from datetime import date
from typing import Any

import pandas as pd

from common.analytics import basic
from common.analytics.analyzers import REGISTRY, run_analyzers
from common.analytics.context import AnalysisContext
from common.config import get_settings
from common.csv_reader import parse_portfolio
from common.market_data import ensure_benchmark, ensure_history, get_current_prices
from common.models import Portfolio, Price
from common.storage import get_storage
from worker.cache import get_cached, holdings_digest, set_cached


def _adj_close(prices: list[Price]) -> pd.Series:
    # adjusted close where present, raw close otherwise, indexed by date
    return pd.Series(
        [p.adj_close if p.adj_close is not None else p.close for p in prices],
        index=pd.Index([p.date for p in prices], name="date"),
        dtype=float,
    ).sort_index()


def window_start(as_of: date, years: int) -> date:
    return (pd.Timestamp(as_of) - pd.DateOffset(years=years)).date()


def _weights(positions: list[dict], total: float) -> pd.Series:
    weights: dict[str, float] = {}
    if total > 0:
        for p in positions:
            symbol = str(p["symbol"]).upper()
            weights[symbol] = weights.get(symbol, 0.0) + p["quantity"] * p["current_price"] / total
    return pd.Series(weights, dtype=float)


def aligned_prices(closes: dict[str, pd.Series]) -> pd.DataFrame:
    # keep only the days every series has a price for. a holding that skipped a
    # day drops that day for everyone, so each return row spans the same dates.
    series = {t: s for t, s in closes.items() if not s.empty}
    if not series:
        return pd.DataFrame()
    return pd.concat(series, axis=1, join="inner").sort_index()


def build_context(
    db, positions: list[dict], as_of: date, history: dict[str, list[Price]], benchmark: list[Price]
) -> AnalysisContext:
    settings = get_settings()
    start = window_start(as_of, settings.analysis_window_years)

    total = basic.calculate_portfolio_total(positions)
    basic.calculate_position_allocation(positions)
    weights = _weights(positions, total)

    full = {t: _adj_close(bars) for t, bars in history.items()}
    window = {t: [b for b in bars if b.date >= start] for t, bars in history.items()}
    prices = aligned_prices({t: _adj_close(bars) for t, bars in window.items()})
    returns = prices.pct_change().iloc[1:]

    # a holding with no history contributes nothing, its weight is not spread
    # over the others
    portfolio_returns = (
        returns.mul(weights.reindex(returns.columns).fillna(0.0), axis=1).sum(axis=1)
        if not returns.empty
        else pd.Series(dtype=float)
    )

    bench_bars = [b for b in benchmark if b.date >= start]
    bench_returns = _adj_close(bench_bars).pct_change().iloc[1:]
    if not portfolio_returns.empty:
        bench_returns = bench_returns[bench_returns.index.isin(portfolio_returns.index)]

    full[settings.benchmark_ticker] = _adj_close(benchmark)
    return AnalysisContext(
        as_of=as_of,
        positions=positions,
        total=total,
        weights=weights,
        prices=prices,
        returns=returns,
        portfolio_returns=portfolio_returns,
        benchmark_returns=bench_returns,
        history=window,
        full_history=full,
        benchmark_ticker=settings.benchmark_ticker,
        db=db,
    )


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
    # download the raw csv, value it at current prices, build the shared context
    # once, then run every registered analyzer over it. returns metric_name -> value.
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

    history = {
        ticker: ensure_history(db, ticker, as_of=as_of)
        for ticker in dict.fromkeys(tickers)  # dedupe, preserve order
    }
    ctx = build_context(db, positions, as_of, history, ensure_benchmark(db, as_of=as_of))

    results = _json_safe(run_analyzers(ctx, REGISTRY))
    set_cached(digest, results)
    return results
