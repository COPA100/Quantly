from typing import Any

from common.analytics import accelerated
from common.analytics.analyzers.base import analyzer
from common.analytics.context import AnalysisContext
from common.analytics.var_models import (
    backtest_var,
    cornish_fisher_var_es,
    historical_var_es,
    horizon_returns,
    parametric_var_es,
)

HORIZONS = {"1d": 1, "21d": 21}
CONFIDENCES = (0.95, 0.99)
SIMULATIONS = 20000
SEED = 0  # fixed so the cached result is reproducible
MIN_OBSERVATIONS = 60


def _cell(returns, horizon: int, confidence: float) -> dict[str, dict[str, float]]:
    mu = float(returns.mean())
    sigma = float(returns.std(ddof=1))
    mc = accelerated.monte_carlo_var(mu, sigma, horizon, SIMULATIONS, confidence, SEED)
    h_var, h_es = historical_var_es(horizon_returns(returns, horizon), confidence)
    p_var, p_es = parametric_var_es(returns, confidence, horizon)
    c_var, c_es = cornish_fisher_var_es(returns, confidence, horizon)
    mc_var = max(mc["var"], 0.0)
    return {
        "historical": {"var": h_var, "es": h_es},
        "parametric": {"var": p_var, "es": p_es},
        "cornish_fisher": {"var": c_var, "es": c_es},
        "monte_carlo": {"var": mc_var, "es": max(mc["cvar"], mc_var)},
    }


def _insight(methods: dict) -> str:
    cell = methods["1d"]["0.99"]
    normal = cell["parametric"]["var"]
    cf = cell["cornish_fisher"]["var"]
    hist = cell["historical"]["var"]
    if normal <= 0:
        return "Daily losses were too small to compare the VaR methods."
    ratio = cf / normal
    if ratio > 1.05:
        shape = (
            "returns have fatter tails than a normal curve, so a normal model "
            "understates the worst days"
        )
    elif ratio < 0.95:
        shape = (
            "returns have thinner tails than a normal curve, so a normal model "
            "overstates the worst days"
        )
    else:
        shape = "returns are close to normal, so the methods agree"
    return (
        f"At 99% over one day, historical VaR is {hist:.1%}, Cornish-Fisher {cf:.1%} and "
        f"normal {normal:.1%}: {shape}."
    )


@analyzer("var_suite", keys=("var_suite",))
def var_suite(ctx: AnalysisContext) -> dict[str, Any]:
    returns = ctx.portfolio_returns
    r = returns.to_numpy(dtype=float)
    if r.size < MIN_OBSERVATIONS:
        raise ValueError(f"need at least {MIN_OBSERVATIONS} days of returns for VaR methods")
    methods = {
        label: {f"{c}": _cell(r, h, c) for c in CONFIDENCES} for label, h in HORIZONS.items()
    }
    backtest = backtest_var(returns)
    out: dict[str, Any] = {
        "methods": methods,
        "backtest": backtest,
        "insight": _insight(methods),
    }
    if backtest is None:
        out["backtest_reason"] = (
            "Not enough history for a rolling 250-day backtest (needs ~350 days)."
        )
    return {"var_suite": out}
