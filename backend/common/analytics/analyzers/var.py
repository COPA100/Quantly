from typing import Any

import numpy as np

from common.analytics import accelerated
from common.analytics.analyzers.base import analyzer
from common.analytics.context import AnalysisContext

# monthly 95% VaR. fixed seed keeps the result deterministic so the analytics
# cache (keyed by holdings+as-of) stays stable across re-runs.
VAR_HORIZON_DAYS = 21
VAR_SIMULATIONS = 20000
VAR_CONFIDENCE = 0.95
VAR_SEED = 0


def value_at_risk(portfolio_returns: np.ndarray) -> dict:
    if portfolio_returns.size < 2:
        return {
            "horizon_days": VAR_HORIZON_DAYS,
            "confidence": VAR_CONFIDENCE,
            "var": 0.0,
            "cvar": 0.0,
        }
    mu = float(np.mean(portfolio_returns))
    sigma = float(np.std(portfolio_returns, ddof=1))
    result = accelerated.monte_carlo_var(
        mu, sigma, VAR_HORIZON_DAYS, VAR_SIMULATIONS, VAR_CONFIDENCE, VAR_SEED
    )
    return {"horizon_days": VAR_HORIZON_DAYS, "confidence": VAR_CONFIDENCE, **result}


@analyzer("var", keys=("var",))
def var(ctx: AnalysisContext) -> dict[str, Any]:
    return {"var": value_at_risk(ctx.portfolio_returns.to_numpy())}
