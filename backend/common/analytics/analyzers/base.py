import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from common.analytics.context import AnalysisContext

logger = logging.getLogger(__name__)

AnalyzerFn = Callable[[AnalysisContext], dict[str, Any]]


@dataclass(frozen=True)
class Analyzer:
    name: str
    # result keys this analyzer writes, every one must be in its return value
    keys: tuple[str, ...]
    fn: AnalyzerFn


def analyzer(name: str, keys: tuple[str, ...]) -> Callable[[AnalyzerFn], Analyzer]:
    # wraps a function into an Analyzer. run order is the explicit list in
    # analyzers/__init__.py, not import order.
    def wrap(fn: AnalyzerFn) -> Analyzer:
        return Analyzer(name=name, keys=keys, fn=fn)

    return wrap


@contextmanager
def observe(analyzer: Analyzer) -> Iterator[None]:
    # hook for tracing/metrics around each analyzer, a no-op by default
    yield


def run_analyzers(ctx: AnalysisContext, registry: list[Analyzer]) -> dict[str, Any]:
    # one failing analyzer marks only its own keys as errored, the rest still run
    for a in registry:
        try:
            with observe(a):
                out = a.fn(ctx)
            missing = [k for k in a.keys if k not in out]
            if missing:
                raise ValueError(f"{a.name} did not return {', '.join(missing)}")
            ctx.results.update({k: out[k] for k in a.keys})
        except Exception as exc:
            logger.exception("analyzer %s failed", a.name)
            message = str(exc)[:200] or type(exc).__name__
            for key in a.keys:
                ctx.results[key] = {"error": message}
    return ctx.results
