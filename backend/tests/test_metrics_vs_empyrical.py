"""cross-check the hand-written metrics against empyrical-reloaded on fixed data.

on a daily series the two agree to float precision for volatility, annualized
return, sharpe, sortino, beta and max drawdown (both anchor the equity curve at
1.0, so even a loss on day one agrees), so those use a tight tolerance. the
differences that exist are conventions, and each one is pinned below with the
relationship it implies rather than a looser tolerance:

- risk free rate: quantly takes an annual rate and divides by periods per year,
  empyrical takes the per-period rate directly.
- degenerate input: a flat series gives 0.0 here, nan or inf in empyrical.
- sortino: both use target downside deviation over all observations
  (sqrt(mean(min(excess, 0) ** 2))), not the std of the negative returns only.
"""

import warnings

import empyrical as ep
import numpy as np
import pytest

from common.analytics import metrics

rng = np.random.default_rng(20260630)
RETURNS = rng.normal(0.0006, 0.013, 756)
BENCH = 0.6 * RETURNS + rng.normal(0.0002, 0.006, 756)
# makes sure the fixed data is not accidentally all one sign
assert (RETURNS < 0).any() and (RETURNS > 0).any()

REL = 1e-9


def test_annualized_volatility_matches():
    assert metrics.annualized_volatility(RETURNS) == pytest.approx(
        ep.annual_volatility(RETURNS), rel=REL
    )


def test_annualized_return_matches():
    assert metrics.annualized_return(RETURNS) == pytest.approx(ep.annual_return(RETURNS), rel=REL)


def test_sharpe_matches_with_and_without_a_risk_free_rate():
    assert metrics.sharpe_ratio(RETURNS) == pytest.approx(ep.sharpe_ratio(RETURNS), rel=REL)
    annual_rf = 0.03
    ours = metrics.sharpe_ratio(RETURNS, risk_free_rate=annual_rf)
    theirs = ep.sharpe_ratio(RETURNS, risk_free=annual_rf / metrics.TRADING_DAYS)
    assert ours == pytest.approx(theirs, rel=REL)


def test_sortino_matches_with_and_without_a_risk_free_rate():
    assert metrics.sortino_ratio(RETURNS) == pytest.approx(ep.sortino_ratio(RETURNS), rel=REL)
    annual_rf = 0.03
    ours = metrics.sortino_ratio(RETURNS, risk_free_rate=annual_rf)
    theirs = ep.sortino_ratio(RETURNS, required_return=annual_rf / metrics.TRADING_DAYS)
    assert ours == pytest.approx(theirs, rel=REL)


def test_sortino_denominator_is_target_downside_deviation():
    # pins the definition: rms of the shortfall over every observation
    downside = np.sqrt(np.mean(np.minimum(RETURNS, 0.0) ** 2))
    expected = np.mean(RETURNS) / downside * np.sqrt(metrics.TRADING_DAYS)
    assert metrics.sortino_ratio(RETURNS) == pytest.approx(expected, rel=REL)
    # and it is not the std of the losing days alone, which would be larger
    losers_only = np.std(RETURNS[RETURNS < 0], ddof=1)
    assert metrics.sortino_ratio(RETURNS) != pytest.approx(
        np.mean(RETURNS) / losers_only * np.sqrt(metrics.TRADING_DAYS), rel=1e-3
    )


def test_max_drawdown_matches():
    assert metrics.max_drawdown(RETURNS)["max_drawdown"] == pytest.approx(
        ep.max_drawdown(RETURNS), rel=REL
    )


def test_max_drawdown_counts_a_day_one_loss():
    # the fall from the starting 1.00 is a drawdown in both
    returns = np.array([-0.10, 0.05, 0.02])
    assert metrics.max_drawdown(returns)["max_drawdown"] == pytest.approx(-0.10)
    assert ep.max_drawdown(returns) == pytest.approx(-0.10)


def test_max_drawdown_matches_on_many_series():
    for seed in range(20):
        r = np.random.default_rng(seed).normal(0.0, 0.02, 120)
        assert metrics.max_drawdown(r)["max_drawdown"] == pytest.approx(ep.max_drawdown(r))


def test_beta_matches():
    assert metrics.beta(RETURNS, BENCH) == pytest.approx(ep.beta(RETURNS, BENCH), rel=REL)
    # and against the textbook cov / var form
    expected = np.cov(RETURNS, BENCH, ddof=1)[0, 1] / np.var(BENCH, ddof=1)
    assert metrics.beta(RETURNS, BENCH) == pytest.approx(expected, rel=REL)


def test_flat_series_gives_zero_where_empyrical_gives_nan_or_inf():
    flat = np.full(50, 0.001)
    assert metrics.sharpe_ratio(flat) == 0.0
    assert metrics.sortino_ratio(flat) == 0.0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        theirs = ep.sharpe_ratio(flat)
    assert not np.isfinite(theirs) or abs(theirs) > 1e6
