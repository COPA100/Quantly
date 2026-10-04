import numpy as np
import pytest

engine = pytest.importorskip("engine")


def test_var_is_identical_for_any_thread_count():
    one = engine.monte_carlo_var(0.0004, 0.012, 21, 50_000, 0.95, 7, threads=1)
    many = engine.monte_carlo_var(0.0004, 0.012, 21, 50_000, 0.95, 7, threads=8)
    assert one == many


def test_qmc_var_is_close_to_mc_and_thread_invariant():
    mc = engine.monte_carlo_var(0.0, 0.01, 21, 1 << 18, 0.95, 3)
    qmc1 = engine.monte_carlo_var_qmc(0.0, 0.01, 21, 1 << 14, 0.95, 3, threads=1)
    qmcn = engine.monte_carlo_var_qmc(0.0, 0.01, 21, 1 << 14, 0.95, 3, threads=4)
    assert qmc1 == qmcn
    assert qmc1["var"] == pytest.approx(mc["var"], rel=0.03)


def test_correlation_is_identical_for_any_thread_count():
    data = np.ascontiguousarray(np.random.default_rng(0).normal(size=(40, 500)))
    one = engine.correlation_matrix(data, threads=1)
    many = engine.correlation_matrix(data, threads=6)
    np.testing.assert_array_equal(one, many)
    np.testing.assert_allclose(one, np.corrcoef(data), atol=1e-12)


def test_non_finite_moments_raise():
    with pytest.raises(ValueError):
        engine.monte_carlo_var(0.0, float("nan"), 21, 1000, 0.95, 1)
