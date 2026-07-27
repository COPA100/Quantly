import numpy as np

from common.analytics import accelerated, metrics


def test_max_drawdown_matches_baseline():
    rng = np.random.default_rng(0)
    returns = rng.normal(0, 0.02, 500)
    fast = accelerated.max_drawdown(returns)
    base = metrics.max_drawdown(returns)
    assert fast["max_drawdown"] == np.float64(base["max_drawdown"]) or np.isclose(
        fast["max_drawdown"], base["max_drawdown"]
    )
    assert fast["duration"] == base["duration"]


def test_correlation_matrix_matches_baseline():
    rng = np.random.default_rng(1)
    returns_by_ticker = {t: rng.normal(0, 0.02, 250) for t in ("AAPL", "MSFT", "TSLA")}
    fast = accelerated.correlation_matrix(returns_by_ticker)
    base = metrics.correlation_matrix(returns_by_ticker)
    assert fast["tickers"] == base["tickers"]
    assert np.allclose(fast["matrix"], base["matrix"])


def test_falls_back_to_python_when_engine_absent(monkeypatch):
    # simulate a checkout without the compiled wheel
    monkeypatch.setattr(accelerated, "_engine", None)
    assert accelerated.using_native() is False

    returns = np.array([0.01, -0.03, 0.02, -0.05, 0.04])
    assert accelerated.max_drawdown(returns) == metrics.max_drawdown(returns)

    var = accelerated.monte_carlo_var(0.0, 0.02, 10, 5000, 0.95, 0)
    assert var["cvar"] >= var["var"] > 0
