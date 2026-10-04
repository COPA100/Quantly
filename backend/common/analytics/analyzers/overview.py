from typing import Any

from common.analytics import basic
from common.analytics.analyzers.base import analyzer
from common.analytics.context import AnalysisContext


@analyzer("overview", keys=("value", "gain_loss", "allocation"))
def overview(ctx: AnalysisContext) -> dict[str, Any]:
    allocation = [
        {"ticker": str(p["symbol"]).upper(), "pct_allocation": p.get("pct_allocation", 0.0)}
        for p in ctx.positions
    ]
    return {
        "value": {"total": round(ctx.total, 2)},
        "gain_loss": basic.calculate_portfolio_gainloss(ctx.positions),
        "allocation": {"positions": allocation},
    }
