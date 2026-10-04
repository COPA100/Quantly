"""shared generators for the property tests."""

import numpy as np
from hypothesis import strategies as st
from hypothesis.extra import numpy as hnp

# daily returns a real book could print. -0.2 keeps every equity curve positive.
daily_return = st.floats(min_value=-0.2, max_value=0.2, allow_nan=False, allow_infinity=False)


def return_series(min_size: int = 2, max_size: int = 120):
    return hnp.arrays(np.float64, st.integers(min_size, max_size), elements=daily_return)


def return_matrix(max_assets: int = 5, min_obs: int = 3, max_obs: int = 80):
    # one return series per ticker, all the same length
    return st.tuples(st.integers(2, max_assets), st.integers(min_obs, max_obs)).flatmap(
        lambda shape: hnp.arrays(np.float64, shape, elements=daily_return)
    )


def has_spread(series: np.ndarray, floor: float = 1e-6) -> bool:
    # the metrics return 0 on a flat series on purpose, properties skip those
    return float(np.std(series, ddof=1)) > floor
