import numpy as np
import pytest

from common.analytics.metrics import (
    annualized_return,
    annualized_volatility,
    average_correlation,
    beta,
    correlation_matrix,
    max_drawdown,
    sharpe_ratio,
    sortino_ratio,
)
from common.analytics.returns import daily_returns, log_returns


def test_daily_returns_known_values():
    assert daily_returns([100, 110, 99]) == pytest.approx([0.1, -0.1])


def test_daily_returns_needs_two_points():
    assert daily_returns([100]).size == 0


def test_log_returns_known_value():
    assert log_returns([100, 110]) == pytest.approx([np.log(1.1)])


def test_volatility_of_constant_series_is_zero():
    assert annualized_volatility([0.01, 0.01, 0.01]) == 0.0


def test_volatility_matches_formula():
    r = [0.01, -0.02, 0.015, -0.005]
    assert annualized_volatility(r) == pytest.approx(np.std(r, ddof=1) * np.sqrt(252))


def test_annualized_return_compounds():
    r = np.full(252, 0.001)
    assert annualized_return(r) == pytest.approx(1.001**252 - 1)


def test_annualized_return_empty_is_zero():
    assert annualized_return([]) == 0.0


def test_annualized_return_total_wipeout():
    assert annualized_return([-1.0, 0.5]) == -1.0


def test_sharpe_matches_formula():
    r = np.array([0.01, -0.005, 0.02, -0.01, 0.015])
    expected = np.mean(r) / np.std(r, ddof=1) * np.sqrt(252)
    assert sharpe_ratio(r) == pytest.approx(expected)


def test_sharpe_of_flat_series_is_zero():
    # a constant series has a tiny non-zero float std, must not blow up
    assert sharpe_ratio(np.full(10, 0.001)) == 0.0


def test_sortino_all_positive_is_zero():
    assert sortino_ratio([0.01, 0.02, 0.03]) == 0.0


def test_sortino_matches_formula():
    r = np.array([0.02, -0.01, 0.03, -0.02, 0.01])
    downside_dev = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2))
    expected = np.mean(r) / downside_dev * np.sqrt(252)
    assert sortino_ratio(r) == pytest.approx(expected)


def test_max_drawdown_counts_initial_decline():
    result = max_drawdown(daily_returns([100, 80, 120]))
    assert result["max_drawdown"] == pytest.approx(-0.2)
    assert result["duration"] == 1


def test_max_drawdown_multi_period():
    result = max_drawdown(daily_returns([100, 110, 90, 95, 120]))
    assert result["max_drawdown"] == pytest.approx(-0.181818, rel=1e-4)
    assert result["duration"] == 2


def test_max_drawdown_monotonic_up_is_zero():
    result = max_drawdown(daily_returns([100, 110, 120, 130]))
    assert result["max_drawdown"] == pytest.approx(0.0)
    assert result["duration"] == 0


def test_max_drawdown_empty():
    assert max_drawdown([]) == {"max_drawdown": 0.0, "duration": 0}


def test_beta_of_series_against_itself_is_one():
    market = np.random.default_rng(0).normal(0, 0.01, 300)
    assert beta(market, market) == pytest.approx(1.0)


def test_beta_of_doubled_series_is_two():
    market = np.random.default_rng(0).normal(0, 0.01, 300)
    assert beta(2 * market, market) == pytest.approx(2.0)


def test_beta_flat_benchmark_is_zero():
    assert beta([0.01, -0.01, 0.02], [0.0, 0.0, 0.0]) == 0.0


def test_correlation_matrix_identical_and_inverse():
    series = np.random.default_rng(0).normal(0, 0.01, 200)
    result = correlation_matrix({"A": series, "B": series, "C": -series})
    matrix = result["matrix"]
    assert result["tickers"] == ["A", "B", "C"]
    assert matrix[0][1] == pytest.approx(1.0)
    assert matrix[0][2] == pytest.approx(-1.0)


def test_average_correlation_off_diagonal():
    matrix = [[1.0, 0.5, 0.3], [0.5, 1.0, 0.1], [0.3, 0.1, 1.0]]
    assert average_correlation(matrix) == pytest.approx((0.5 + 0.3 + 0.1) / 3)


def test_correlation_matrix_single_ticker():
    assert correlation_matrix({"A": [0.01, 0.02]})["matrix"] == [[1.0]]
