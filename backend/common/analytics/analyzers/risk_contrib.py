from typing import Any

import numpy as np
from scipy.stats import norm

from common.analytics.analyzers.base import analyzer
from common.analytics.context import AnalysisContext
from common.analytics.metrics import TRADING_DAYS

VAR_CONFIDENCE = 0.95
# a holding within this many points of its capital share is "in line"
IN_LINE = 0.02


def euler_decomposition(weights: np.ndarray, cov: np.ndarray) -> tuple[float, np.ndarray]:
    # sigma_p = sqrt(w' S w), RC_i = w_i (S w)_i / sigma_p, and sum(RC) == sigma_p
    marginal = cov @ weights
    sigma = float(np.sqrt(weights @ marginal))
    return sigma, weights * marginal / sigma


def risk_insight(holdings: list[dict]) -> str:
    # lead with the holding whose share of risk most exceeds its share of money
    top = max(holdings, key=lambda h: h["pct_risk"] - h["weight"])
    money, risk = round(top["weight"] * 100), round(top["pct_risk"] * 100)
    if top["pct_risk"] - top["weight"] < IN_LINE:
        return "Risk is spread roughly in line with how your money is split."
    return f"{top['ticker']} is {money}% of your money but {risk}% of your risk."


@analyzer("risk_contribution", keys=("risk_contribution",))
def risk_contribution(ctx: AnalysisContext) -> dict[str, Any]:
    returns = ctx.returns
    if returns.shape[1] == 0 or len(returns) < 2:
        return {"risk_contribution": {"holdings": [], "insight": ""}}
    w = ctx.weights.reindex(returns.columns).fillna(0.0).to_numpy(dtype=float)
    if w.sum() <= 0:
        return {"risk_contribution": {"holdings": [], "insight": ""}}
    w = w / w.sum()
    daily_cov = np.cov(returns.to_numpy(dtype=float), rowvar=False, ddof=1).reshape(len(w), len(w))
    variance = float(w @ daily_cov @ w)
    if variance <= 1e-18:
        return {"risk_contribution": {"holdings": [], "insight": ""}}
    daily_sigma = variance**0.5

    sigma, rc = euler_decomposition(w, daily_cov * TRADING_DAYS)
    # parametric var of the book moves by this much per unit of weight in i
    z = float(norm.ppf(VAR_CONFIDENCE))
    marginal_var = z * (daily_cov @ w) / daily_sigma

    holdings = [
        {
            "ticker": str(t),
            "weight": float(w[i]),
            "pct_risk": float(rc[i] / sigma),
            "rc": float(rc[i]),
            "marginal_var": float(marginal_var[i]),
        }
        for i, t in enumerate(returns.columns)
    ]
    holdings.sort(key=lambda h: h["pct_risk"], reverse=True)
    return {"risk_contribution": {"holdings": holdings, "insight": risk_insight(holdings)}}
