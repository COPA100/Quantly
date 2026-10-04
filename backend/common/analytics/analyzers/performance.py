from typing import Any

import pandas as pd

from common.analytics import accelerated, metrics
from common.analytics.analyzers.base import analyzer
from common.analytics.context import AnalysisContext


@analyzer(
    "performance",
    keys=("volatility", "returns", "sharpe", "sortino", "drawdown", "beta"),
)
def performance(ctx: AnalysisContext) -> dict[str, Any]:
    r = ctx.portfolio_returns.to_numpy()
    # beta on the days both series have, matched by date
    paired = pd.concat([ctx.portfolio_returns, ctx.benchmark_returns], axis=1, join="inner")
    return {
        "volatility": {"annualized": metrics.annualized_volatility(r)},
        "returns": {"annualized": metrics.annualized_return(r)},
        "sharpe": {"ratio": metrics.sharpe_ratio(r)},
        "sortino": {"ratio": metrics.sortino_ratio(r)},
        # path-dependent scan, runs in the c++ engine when installed
        "drawdown": accelerated.max_drawdown(r),
        "beta": {"beta": metrics.beta(paired.iloc[:, 0].to_numpy(), paired.iloc[:, 1].to_numpy())},
    }
