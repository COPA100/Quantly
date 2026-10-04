from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from common.analytics.analyzers import REGISTRY
from common.analytics.analyzers.stress import SCENARIOS, stress
from common.analytics.context import AnalysisContext

COVID_START = date(2020, 2, 19)
COVID_END = date(2020, 3, 23)


def _path(start_px: float, end_px: float, first: date = date(2020, 2, 1)) -> pd.Series:
    # flat at start_px until the covid start, then at end_px from the covid end
    days = [first + timedelta(days=i) for i in range((date(2020, 4, 1) - first).days)]
    values = [start_px if d <= COVID_START else end_px if d >= COVID_END else 90.0 for d in days]
    return pd.Series(values, index=pd.Index(days, name="date"), dtype=float)


def _ctx(weights, full_history, returns=None, bench_returns=None) -> AnalysisContext:
    returns = pd.DataFrame() if returns is None else returns
    bench = pd.Series(dtype=float) if bench_returns is None else bench_returns
    return AnalysisContext(
        as_of=date(2026, 6, 30),
        positions=[],
        total=1.0,
        weights=pd.Series(weights, dtype=float),
        prices=pd.DataFrame(),
        returns=returns,
        portfolio_returns=pd.Series(dtype=float),
        benchmark_returns=bench,
        history={},
        full_history=full_history,
        benchmark_ticker="SPY",
    )


def _covid(out: dict) -> dict:
    return next(s for s in out["stress"]["scenarios"] if s["name"] == "COVID crash")


def test_exact_loss_on_a_synthetic_path():
    hist = {"SPY": _path(100, 80), "AAA": _path(50, 35), "BBB": _path(10, 9)}
    out = stress.fn(_ctx({"AAA": 0.6, "BBB": 0.4}, hist))
    covid = _covid(out)
    assert covid["portfolio_return"] == pytest.approx(0.6 * -0.30 + 0.4 * -0.10)
    assert covid["benchmark_return"] == pytest.approx(-0.20)
    assert covid["worst"]["ticker"] == "AAA"
    assert covid["worst"]["return"] == pytest.approx(-0.30)
    assert covid["proxied_weight"] == 0.0
    assert {h["method"] for h in covid["holdings"]} == {"replayed"}
    # the benchmark has no data for the other windows, so they are skipped
    assert [s["name"] for s in out["stress"]["scenarios"]] == ["COVID crash"]
    insight = out["stress"]["insight"]
    assert "COVID crash" in insight and "22%" in insight and "20%" in insight


def _beta_inputs(betas: dict[str, float]):
    rng = np.random.default_rng(1)
    idx = pd.Index([date(2019, 1, 1) + timedelta(days=i) for i in range(200)], name="date")
    bench = pd.Series(rng.normal(0, 0.01, len(idx)), index=idx)
    returns = pd.DataFrame({t: b * bench for t, b in betas.items()})
    return returns, bench


def test_proxy_is_used_exactly_when_coverage_is_missing():
    returns, bench = _beta_inputs({"BBB": 1.5})
    # BBB's history starts after the covid start, AAA covers it
    hist = {
        "SPY": _path(100, 80),
        "AAA": _path(50, 40),
        "BBB": _path(10, 5, first=date(2020, 3, 1)),
    }
    out = stress.fn(_ctx({"AAA": 0.5, "BBB": 0.5}, hist, returns, bench))
    by_ticker = {h["ticker"]: h for h in _covid(out)["holdings"]}
    assert by_ticker["AAA"]["method"] == "replayed"
    assert by_ticker["AAA"]["return"] == pytest.approx(-0.20)
    assert by_ticker["BBB"]["method"] == "proxied"
    # beta 1.5 x spy's -20%, not the -50% its own late history would suggest
    assert by_ticker["BBB"]["return"] == pytest.approx(1.5 * -0.20)
    assert _covid(out)["proxied_weight"] == pytest.approx(0.5)


def test_all_proxied_portfolio_is_weighted_beta_times_benchmark():
    returns, bench = _beta_inputs({"AAA": 2.0, "BBB": 0.5})
    out = stress.fn(_ctx({"AAA": 0.7, "BBB": 0.3}, {"SPY": _path(100, 80)}, returns, bench))
    covid = _covid(out)
    assert covid["portfolio_return"] == pytest.approx((0.7 * 2.0 + 0.3 * 0.5) * -0.20)
    assert covid["proxied_weight"] == pytest.approx(1.0)


def test_holding_with_no_data_is_proxied_at_beta_one_and_flagged():
    out = stress.fn(_ctx({"ZZZ": 1.0}, {"SPY": _path(100, 80)}))
    (h,) = _covid(out)["holdings"]
    assert h["method"] == "proxied"
    assert h["return"] == pytest.approx(-0.20)
    assert h["no_history"] is True


def test_scenarios_are_skipped_without_benchmark_data():
    out = stress.fn(_ctx({"AAA": 1.0}, {"AAA": _path(50, 40)}))
    assert out["stress"] == {"scenarios": [], "insight": ""}


def test_scenario_constants_and_registration():
    assert all(s.start < s.end for s in SCENARIOS)
    assert len(SCENARIOS) == 6
    names = [a.name for a in REGISTRY]
    assert names.index("stress") > names.index("insights")
    assert REGISTRY[names.index("stress")].keys == ("stress",)
