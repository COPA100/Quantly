from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import select

from common.analytics.analyzers.base import analyzer
from common.analytics.context import AnalysisContext
from common.analytics.metrics import TRADING_DAYS
from common.market_data.factors import ensure_factors
from common.models import FactorReturn

FACTORS = ("mkt_rf", "smb", "hml", "rmw", "cma", "mom")
NW_LAGS = 5
MIN_OBS = 60
Z_95 = 1.96
# |t| above this counts as a real tilt
T_SIGNIFICANT = 2.0
MIN_TILT = 0.1

# (label when beta is positive, label when negative)
TILTS = {
    "smb": ("small caps", "large caps"),
    "hml": ("value", "growth"),
    "rmw": ("profitable firms", "weakly profitable firms"),
    "cma": ("conservative investors", "aggressive investors"),
    "mom": ("momentum", "reversal"),
}


def ols_newey_west(y: np.ndarray, x: np.ndarray, lags: int = NW_LAGS):
    # ols with an intercept column already in x. returns coefficients,
    # newey-west (bartlett kernel) standard errors, and r squared.
    n, k = x.shape
    xtx_inv = np.linalg.inv(x.T @ x)
    beta = xtx_inv @ x.T @ y
    resid = y - x @ beta
    scores = x * resid[:, None]
    s = scores.T @ scores
    for lag in range(1, lags + 1):
        gamma = scores[lag:].T @ scores[:-lag]
        s += (1.0 - lag / (lags + 1.0)) * (gamma + gamma.T)
    cov = xtx_inv @ s @ xtx_inv
    se = np.sqrt(np.diag(cov))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - float(resid @ resid) / ss_tot if ss_tot > 0 else 0.0
    return beta, se, r2


def _unavailable(reason: str) -> dict[str, Any]:
    return {"factors": {"available": False, "reason": reason}}


def _factor_frame(ctx: AnalysisContext) -> pd.DataFrame:
    first, last = ctx.portfolio_returns.index.min(), ctx.portfolio_returns.index.max()
    rows = ctx.db.scalars(
        select(FactorReturn)
        .where(FactorReturn.date >= first, FactorReturn.date <= last)
        .order_by(FactorReturn.date)
    ).all()
    return pd.DataFrame(
        [{"date": r.date, "rf": r.rf, **{f: getattr(r, f) for f in FACTORS}} for r in rows]
    ).set_index("date")


def factor_insight(loadings: list[dict], alpha_annual: float, alpha_t: float) -> str:
    tilts = [
        (abs(row["t_stat"]), TILTS[row["factor"]][0 if row["beta"] > 0 else 1])
        for row in loadings
        if row["factor"] in TILTS
        and abs(row["t_stat"]) >= T_SIGNIFICANT
        and abs(row["beta"]) >= MIN_TILT
    ]
    tilts.sort(reverse=True)
    names = [name for _, name in tilts]
    if not names:
        head = "No clear style tilt beyond the market"
    elif len(names) == 1:
        head = f"Tilted toward {names[0]}"
    else:
        head = f"Tilted toward {', '.join(names[:-1])} and {names[-1]}"
    if abs(alpha_t) < T_SIGNIFICANT:
        tail = "alpha is not statistically different from zero"
    else:
        sign = "positive" if alpha_annual > 0 else "negative"
        tail = f"alpha of {alpha_annual * 100:.1f}% a year is statistically {sign}"
    return f"{head}; {tail}."


@analyzer("factors", keys=("factors",))
def factors(ctx: AnalysisContext) -> dict[str, Any]:
    if ctx.db is None:
        return _unavailable("no database session")
    if ctx.portfolio_returns.empty:
        return _unavailable("no portfolio returns")
    ensure_factors(ctx.db)
    frame = _factor_frame(ctx)
    paired = frame.join(ctx.portfolio_returns.rename("port"), how="inner").dropna()
    if len(paired) < MIN_OBS:
        return _unavailable(f"only {len(paired)} days overlap the factor data, need {MIN_OBS}")

    y = (paired["port"] - paired["rf"]).to_numpy(dtype=float)
    x = np.column_stack([np.ones(len(paired)), paired[list(FACTORS)].to_numpy(dtype=float)])
    beta, se, r2 = ols_newey_west(y, x)

    loadings = []
    for i, name in enumerate(FACTORS, start=1):
        b, s = float(beta[i]), float(se[i])
        loadings.append(
            {
                "factor": name,
                "beta": b,
                "t_stat": b / s if s > 0 else 0.0,
                "ci_low": b - Z_95 * s,
                "ci_high": b + Z_95 * s,
            }
        )
    alpha_annual = float(beta[0]) * TRADING_DAYS
    alpha_t = float(beta[0] / se[0]) if se[0] > 0 else 0.0
    return {
        "factors": {
            "available": True,
            "loadings": loadings,
            "alpha_annual": alpha_annual,
            "alpha_t": alpha_t,
            "r_squared": r2,
            "n_obs": len(paired),
            "start": paired.index.min().isoformat(),
            "end": paired.index.max().isoformat(),
            "insight": factor_insight(loadings, alpha_annual, alpha_t),
        }
    }
