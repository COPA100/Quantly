"""pluggable analysis steps.

each module defines one `@analyzer(...)` function. REGISTRY below is the run
order, and an analyzer can read the results of the ones before it through
`ctx.results`. to add one: write the module and append it to REGISTRY.
"""

from common.analytics.analyzers import (
    correlation,
    equity_curve,
    factors,
    frontier,
    insights,
    overview,
    performance,
    risk_contrib,
    stress,
    var,
    var_suite,
)
from common.analytics.analyzers.base import Analyzer, analyzer, run_analyzers

REGISTRY: list[Analyzer] = [
    overview.overview,
    performance.performance,
    var.var,
    equity_curve.equity,
    correlation.correlation,
    # reads the core metrics above, keep it after them
    insights.insights,
    stress.stress,
    var_suite.var_suite,
    frontier.frontier,
    factors.factors,
    risk_contrib.risk_contribution,
]

__all__ = ["REGISTRY", "Analyzer", "analyzer", "run_analyzers"]
