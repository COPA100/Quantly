from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import pandas as pd

from common.analytics import metrics
from common.analytics.analyzers.base import analyzer
from common.analytics.context import AnalysisContext

# how far from a scenario date a bar may sit and still count as that day's price
TOLERANCE = timedelta(days=5)


@dataclass(frozen=True)
class Scenario:
    name: str
    start: date
    end: date


# spy peak-to-trough windows of the major drawdowns since 2007
SCENARIOS: tuple[Scenario, ...] = (
    Scenario("global financial crisis", date(2007, 10, 9), date(2009, 3, 9)),
    Scenario("US downgrade", date(2011, 7, 22), date(2011, 10, 3)),
    Scenario("China devaluation", date(2015, 8, 17), date(2015, 8, 25)),
    Scenario("Q4 2018 selloff", date(2018, 9, 20), date(2018, 12, 24)),
    Scenario("COVID crash", date(2020, 2, 19), date(2020, 3, 23)),
    Scenario("2022 rate shock", date(2022, 1, 3), date(2022, 10, 12)),
)


def _price_on_or_before(dates: list[date], values: list[float], day: date) -> float | None:
    i = bisect_right(dates, day)
    if i and dates[i - 1] >= day - TOLERANCE:
        return values[i - 1]
    return None


def scenario_return(series: pd.Series | None, start: date, end: date) -> float | None:
    # last close on or before each date, the start may also fall back to the first
    # close after it. None when the series does not cover the window.
    if series is None or series.empty:
        return None
    dates = list(series.index)
    values = [float(v) for v in series.to_numpy()]
    p0 = _price_on_or_before(dates, values, start)
    if p0 is None:
        j = bisect_left(dates, start)
        if j < len(dates) and dates[j] <= start + TOLERANCE:
            p0 = values[j]
    p1 = _price_on_or_before(dates, values, end)
    if p0 is None or p1 is None or p0 <= 0:
        return None
    return p1 / p0 - 1.0


def _betas(ctx: AnalysisContext) -> dict[str, float]:
    # beta to the benchmark over the analysis window, paired by date
    out: dict[str, float] = {}
    for ticker in ctx.returns.columns:
        paired = pd.concat([ctx.returns[ticker], ctx.benchmark_returns], axis=1, join="inner")
        if len(paired) >= 2:
            out[ticker] = metrics.beta(paired.iloc[:, 0].to_numpy(), paired.iloc[:, 1].to_numpy())
    return out


def _insight(scenarios: list[dict[str, Any]]) -> str:
    if not scenarios:
        return ""
    worst = min(scenarios, key=lambda s: s["portfolio_return"])
    p, b = worst["portfolio_return"], worst["benchmark_return"]
    verb = "lost" if p < 0 else "gained"
    return (
        f"In the {worst['name']} this portfolio would have {verb} about "
        f"{abs(p) * 100:.0f}%, vs {b * 100:+.0f}% for the S&P 500."
    )


@analyzer("stress", keys=("stress",))
def stress(ctx: AnalysisContext) -> dict[str, Any]:
    betas = _betas(ctx)
    bench_series = ctx.full_history.get(ctx.benchmark_ticker)
    holdings = sorted(ctx.weights.items(), key=lambda kv: (-kv[1], kv[0]))

    scenarios: list[dict[str, Any]] = []
    for sc in SCENARIOS:
        bench_ret = scenario_return(bench_series, sc.start, sc.end)
        if bench_ret is None:
            continue
        rows: list[dict[str, Any]] = []
        for ticker, weight in holdings:
            own = scenario_return(ctx.full_history.get(ticker), sc.start, sc.end)
            row: dict[str, Any] = {"ticker": ticker, "weight": float(weight)}
            if own is not None:
                row.update(**{"return": own}, method="replayed")
            else:
                # no usable return series either means beta 1.0, flagged
                beta = betas.get(ticker, 1.0)
                # a high beta times a deep crash can pass -100%, which no long
                # position can lose, so the estimate stops at a total loss
                proxied = max(beta * bench_ret, -1.0)
                row.update(**{"return": proxied}, method="proxied", beta=beta)
                if ticker not in betas:
                    row["no_history"] = True
            rows.append(row)

        worst = min(rows, key=lambda r: r["return"], default=None)
        scenarios.append(
            {
                "name": sc.name,
                "start": sc.start.isoformat(),
                "end": sc.end.isoformat(),
                "portfolio_return": sum(r["weight"] * r["return"] for r in rows),
                "benchmark_return": bench_ret,
                "worst": {"ticker": worst["ticker"], "return": worst["return"]} if worst else None,
                "proxied_weight": sum(r["weight"] for r in rows if r["method"] == "proxied"),
                "holdings": rows,
            }
        )
    return {"stress": {"scenarios": scenarios, "insight": _insight(scenarios)}}
