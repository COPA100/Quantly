import numpy as np
import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from common.analytics import accelerated, metrics, risk
from tests.property.strategies import has_spread, return_matrix, return_series

NATIVE = accelerated.using_native()

confidence_pair = st.tuples(st.floats(0.5, 0.995), st.floats(0.5, 0.995)).map(sorted)


def _corr_paths(matrix: np.ndarray):
    # numpy baseline always, the c++ kernel too when the wheel is installed
    series = {f"T{i}": row for i, row in enumerate(matrix)}
    yield metrics.correlation_matrix(series)["matrix"]
    if NATIVE:
        yield accelerated.correlation_matrix(series)["matrix"]


@pytest.mark.filterwarnings("ignore::RuntimeWarning")  # numpy divides by a zero std on flat rows
@given(return_matrix())
def test_correlation_is_bounded_symmetric_with_unit_diagonal(matrix):
    for corr in _corr_paths(matrix):
        m = np.array(corr)
        flat = np.isnan(np.diag(m))
        finite = ~np.isnan(m)
        assert np.all(np.abs(m[finite]) <= 1.0 + 1e-9)
        np.testing.assert_allclose(m, m.T, atol=1e-9, equal_nan=True)
        np.testing.assert_allclose(np.diag(m)[~flat], 1.0, atol=1e-9)
        # nan only ever comes from a constant series. the converse does not hold: a
        # constant like 0.16077 leaves ~1e-17 of rounding residue and yields a finite value.
        assert np.all(np.var(matrix, axis=1)[flat] == 0.0)


@given(return_series(min_size=1))
def test_max_drawdown_is_nonpositive_and_bounded(returns):
    out = metrics.max_drawdown(returns)
    assert -1.0 <= out["max_drawdown"] <= 0.0
    assert 0 <= out["duration"] <= returns.size
    # a drawdown means some period under water, and the reverse
    assert (out["max_drawdown"] < 0) == (out["duration"] > 0)


@given(return_series(min_size=1))
def test_drawdown_is_zero_when_returns_never_negative(returns):
    out = metrics.max_drawdown(np.abs(returns))
    assert out == {"max_drawdown": 0.0, "duration": 0}


@given(return_series(min_size=1))
def test_native_drawdown_matches_python(returns):
    if not NATIVE:
        pytest.skip("engine wheel not installed")
    fast = accelerated.max_drawdown(returns)
    base = metrics.max_drawdown(returns)
    assert fast["duration"] == base["duration"]
    assert fast["max_drawdown"] == pytest.approx(base["max_drawdown"], abs=1e-12)


@given(return_series(), st.floats(-0.05, 0.05))
def test_volatility_ignores_a_constant_shift(returns, shift):
    base = metrics.annualized_volatility(returns)
    shifted = metrics.annualized_volatility(returns + shift)
    assert shifted == pytest.approx(base, rel=1e-6, abs=1e-9)


@given(return_series(), st.floats(0.1, 10.0))
def test_volatility_scales_linearly(returns, scale):
    base = metrics.annualized_volatility(returns)
    assert metrics.annualized_volatility(returns * scale) == pytest.approx(
        scale * base, rel=1e-6, abs=1e-9
    )


@given(return_series(), st.floats(0.1, 10.0))
def test_sharpe_is_scale_invariant(returns, scale):
    assume(has_spread(returns) and has_spread(returns * scale))
    assert metrics.sharpe_ratio(returns * scale) == pytest.approx(
        metrics.sharpe_ratio(returns), rel=1e-6, abs=1e-6
    )


@given(return_series(), st.floats(-0.01, 0.01))
def test_sharpe_moves_by_shift_over_vol(returns, shift):
    # adding k to every return adds k to the mean and leaves the std alone
    assume(has_spread(returns))
    std = float(np.std(returns, ddof=1))
    expected = metrics.sharpe_ratio(returns) + shift / std * np.sqrt(metrics.TRADING_DAYS)
    assert metrics.sharpe_ratio(returns + shift) == pytest.approx(expected, rel=1e-6, abs=1e-6)


@given(return_series())
def test_beta_of_a_series_against_itself_is_one(returns):
    assume(has_spread(returns))
    assert metrics.beta(returns, returns) == pytest.approx(1.0, rel=1e-9)


@given(return_series(), return_series(), st.floats(0.1, 10.0))
def test_beta_scales_with_the_asset(asset, bench, scale):
    assume(has_spread(bench))
    assert metrics.beta(asset * scale, bench) == pytest.approx(
        scale * metrics.beta(asset, bench), rel=1e-6, abs=1e-9
    )


@given(
    st.floats(-0.002, 0.002),
    st.floats(0.002, 0.05),
    st.integers(1, 30),
    st.integers(0, 5),
    confidence_pair,
)
def test_var_is_monotone_in_confidence(mu, sigma, horizon, seed, confs):
    lo, hi = confs
    # same seed means the same draws, only the quantile index moves
    a = risk.monte_carlo_var(mu, sigma, horizon, 1500, lo, seed)
    b = risk.monte_carlo_var(mu, sigma, horizon, 1500, hi, seed)
    assert a["var"] <= b["var"] + 1e-12
    assert a["cvar"] <= b["cvar"] + 1e-12
    assert b["cvar"] >= b["var"] - 1e-12


@given(st.floats(0.002, 0.05), confidence_pair)
def test_native_var_is_monotone_in_confidence(sigma, confs):
    if not NATIVE:
        pytest.skip("engine wheel not installed")
    lo, hi = confs
    a = accelerated.monte_carlo_var(0.0, sigma, 10, 1500, lo, 3)
    b = accelerated.monte_carlo_var(0.0, sigma, 10, 1500, hi, 3)
    assert a["var"] <= b["var"] + 1e-12
    assert a["cvar"] <= b["cvar"] + 1e-12
