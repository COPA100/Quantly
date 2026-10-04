from typing import Any

from common.analytics.analyzers.base import analyzer
from common.analytics.context import AnalysisContext
from common.models import Price


def equity_curve(positions: list[dict], history_by_ticker: dict[str, list[Price]]) -> dict:
    # portfolio market value over time = sum(shares * close), on the dates every
    # holding has a price for. this is the series the frontend charts.
    shares_by_ticker: dict[str, float] = {}
    for p in positions:
        symbol = str(p["symbol"]).upper()
        shares_by_ticker[symbol] = shares_by_ticker.get(symbol, 0.0) + float(p["quantity"])

    closes_by_ticker: dict[str, dict] = {}
    date_sets: list[set] = []
    for ticker, prices in history_by_ticker.items():
        closes = {pr.date: pr.close for pr in prices if pr.close is not None}
        if closes:
            closes_by_ticker[ticker] = closes
            date_sets.append(set(closes))
    if not date_sets:
        return {"dates": [], "values": []}

    common = sorted(set.intersection(*date_sets))
    dates = [d.isoformat() for d in common]
    values = [
        round(
            sum(shares_by_ticker.get(t, 0.0) * closes_by_ticker[t][d] for t in closes_by_ticker), 2
        )
        for d in common
    ]
    return {"dates": dates, "values": values}


@analyzer("equity_curve", keys=("equity_curve",))
def equity(ctx: AnalysisContext) -> dict[str, Any]:
    return {"equity_curve": equity_curve(ctx.positions, ctx.history)}
