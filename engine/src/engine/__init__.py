"""Quantly C++ analytics engine.

Thin Python package wrapping the pybind11 extension `engine._engine`. The worker
imports from here so it can fall back to a pure-Python path when the compiled
module is unavailable.
"""

from ._engine import (
    __version__,
    correlation_matrix,
    covariance_matrix,
    hello,
    max_drawdown,
    monte_carlo_var,
)

__all__ = [
    "__version__",
    "correlation_matrix",
    "covariance_matrix",
    "hello",
    "max_drawdown",
    "monte_carlo_var",
]
