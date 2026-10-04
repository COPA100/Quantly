from typing import Any

from common.analytics import insights as text
from common.analytics.analyzers.base import analyzer
from common.analytics.context import AnalysisContext


@analyzer("insights", keys=("insights",))
def insights(ctx: AnalysisContext) -> dict[str, Any]:
    # plain-english layer over the core metrics, so it runs after them
    r = ctx.results
    weights_sorted = sorted((p.get("pct_allocation", 0.0) for p in ctx.positions), reverse=True)
    top_n = min(3, len(weights_sorted))
    top_weight = sum(weights_sorted[:top_n])
    corr = r["correlation"]
    return {
        "insights": {
            "volatility": text.volatility_insight(r["volatility"]["annualized"]),
            "drawdown": text.drawdown_insight(r["drawdown"]["max_drawdown"]),
            "sharpe": text.sharpe_insight(r["sharpe"]["ratio"]),
            "sortino": text.sortino_insight(r["sortino"]["ratio"]),
            "beta": text.beta_insight(r["beta"]["beta"]),
            "correlation": text.correlation_insight(len(corr["tickers"]), corr["average"]),
            "concentration": text.concentration_insight(top_weight, top_n),
        }
    }
