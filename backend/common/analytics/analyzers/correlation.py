from typing import Any

from common.analytics import accelerated, metrics
from common.analytics.analyzers.base import analyzer
from common.analytics.context import AnalysisContext


@analyzer("correlation", keys=("correlation",))
def correlation(ctx: AnalysisContext) -> dict[str, Any]:
    # columns are already date-aligned, so the kernel sees matching days
    corr = accelerated.correlation_matrix({t: ctx.returns[t].to_numpy() for t in ctx.returns})
    return {
        "correlation": {
            "tickers": corr["tickers"],
            "matrix": corr["matrix"],
            "average": metrics.average_correlation(corr["matrix"]),
        }
    }
