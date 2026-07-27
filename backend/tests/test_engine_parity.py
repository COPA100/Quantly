"""Parity between the C++ engine and the pure-python / numpy baselines.

These are the pybind boundary tests: they assert the compiled kernels agree with
the reference implementations the worker would otherwise use. VaR uses Monte
Carlo with a different RNG per language, so it is checked for statistical
agreement rather than bit-equality.
"""

import numpy as np
import pytest

from common.analytics import metrics, risk

engine = pytest.importorskip("engine")


@pytest.mark.parametrize("n", [0, 1, 2, 5, 50, 500, 3000])
def test_max_drawdown_parity(n):
    rng = np.random.default_rng(n)
    returns = rng.normal(0, 0.02, n)
    cpp = engine.max_drawdown(returns)
    py = metrics.max_drawdown(returns)
    assert np.isclose(cpp["max_drawdown"], py["max_drawdown"], rtol=1e-12, atol=1e-12)
    assert cpp["duration"] == py["duration"]


def test_max_drawdown_parity_on_wipeout():
    returns = [0.1, -0.5, -0.5, 0.2, 0.3]
    cpp = engine.max_drawdown(returns)
    py = metrics.max_drawdown(returns)
    assert cpp["max_drawdown"] == py["max_drawdown"]
    assert cpp["duration"] == py["duration"]


@pytest.mark.parametrize("n_assets", [2, 3, 5, 10])
@pytest.mark.parametrize("n_obs", [5, 60, 252])
def test_correlation_matrix_parity(n_assets, n_obs):
    rng = np.random.default_rng(n_assets * 100 + n_obs)
    data = rng.normal(0, 0.02, (n_assets, n_obs))
    cpp = engine.correlation_matrix(data)
    npy = np.corrcoef(data)
    assert np.allclose(cpp, npy, rtol=1e-9, atol=1e-12)


@pytest.mark.parametrize("ddof", [0, 1])
def test_covariance_matrix_parity(ddof):
    rng = np.random.default_rng(7)
    data = rng.normal(0, 0.02, (6, 200))
    cpp = engine.covariance_matrix(data, ddof)
    npy = np.cov(data, ddof=ddof)
    assert np.allclose(cpp, npy, rtol=1e-9, atol=1e-15)


@pytest.mark.parametrize(
    "mu,sigma,horizon",
    [(0.0, 0.02, 1), (0.0005, 0.015, 10), (0.001, 0.03, 21), (-0.0002, 0.025, 5)],
)
def test_monte_carlo_var_statistical_parity(mu, sigma, horizon):
    # different RNGs, so both estimate the same quantity to within MC noise
    cpp = engine.monte_carlo_var(mu, sigma, horizon, 200_000, 0.95, 123)
    py = risk.monte_carlo_var(mu, sigma, horizon, 200_000, 0.95, 123)
    assert cpp["var"] == pytest.approx(py["var"], abs=3e-3)
    assert cpp["cvar"] == pytest.approx(py["cvar"], abs=3e-3)
    assert cpp["cvar"] >= cpp["var"] > 0
