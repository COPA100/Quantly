"""Tracing and metrics. Every entry point is a no-op unless QUANTLY_OTEL_ENABLED=true.

Metrics live on their own registry, created once at import, so re-imports and test
runs never hit duplicate-registration errors and the default registry stays clean.
"""

import logging
import os
import shutil
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import redis
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
    multiprocess,
    start_http_server,
)
from prometheus_client.core import GaugeMetricFamily

from common.config import get_settings

logger = logging.getLogger(__name__)

REGISTRY = CollectorRegistry()

_HTTP_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.2, 0.3, 0.5, 1, 2.5, 5, 10)
_JOB_BUCKETS = (0.5, 1, 2.5, 5, 10, 20, 30, 45, 60, 90, 120, 300)
_ANALYZER_BUCKETS = (0.001, 0.005, 0.025, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30)

# histograms (not summaries) so quantiles can be aggregated across replicas.
# 0.3 and 60 are bucket bounds because the SLO thresholds sit exactly there.
HTTP_DURATION = Histogram(
    "quantly_http_request_duration_seconds",
    "api request latency, measured to the response headers",
    ["method", "route", "status"],
    buckets=_HTTP_BUCKETS,
    registry=REGISTRY,
)
JOB_DURATION = Histogram(
    "quantly_job_duration_seconds",
    "celery task wall time",
    ["task"],
    buckets=_JOB_BUCKETS,
    registry=REGISTRY,
)
JOBS = Counter("quantly_jobs_total", "celery task outcomes", ["task", "outcome"], registry=REGISTRY)
JOB_RETRIES = Counter("quantly_job_retries_total", "task retries", ["task"], registry=REGISTRY)
DLQ = Counter("quantly_dlq_total", "jobs pushed to the dead letter list", registry=REGISTRY)
ANALYZER_DURATION = Histogram(
    "quantly_analyzer_duration_seconds",
    "time spent in one analyzer",
    ["analyzer", "outcome"],
    buckets=_ANALYZER_BUCKETS,
    registry=REGISTRY,
)
CACHE = Counter(
    "quantly_cache_requests_total", "cache lookups", ["cache", "result"], registry=REGISTRY
)


def enabled() -> bool:
    return get_settings().otel_enabled


# ---- recording helpers: cheap no-ops when disabled ----


def record_cache(hit: bool, cache: str = "analytics") -> None:
    if enabled():
        CACHE.labels(cache, "hit" if hit else "miss").inc()


def record_dlq() -> None:
    if enabled():
        DLQ.inc()


# ---- queue depth: sampled at scrape time ----


class QueueDepthCollector:
    """Reads LLEN of the celery queue each time prometheus scrapes."""

    def __init__(self) -> None:
        self._client: redis.Redis | None = None

    def collect(self):
        settings = get_settings()
        family = GaugeMetricFamily(
            "quantly_queue_depth", "tasks waiting in the broker queue", labels=["queue"]
        )
        try:
            if self._client is None:
                self._client = redis.Redis.from_url(settings.celery_broker_url)
            depth = self._client.llen(settings.celery_queue_name)
        except redis.RedisError:
            logger.warning("queue depth sample failed")
            return
        family.add_metric([settings.celery_queue_name], depth)
        yield family


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST


# ---- tracing ----

_provider = None


def _get_tracer():
    from opentelemetry import trace

    if _provider is not None:
        return _provider.get_tracer("quantly")
    return trace.get_tracer("quantly")


def setup_tracing(service_name: str, exporter: Any = None, instrument: bool = True) -> None:
    """Build the tracer provider and instrument libraries. `exporter` is for tests."""
    global _provider
    if not enabled():
        return
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor

    settings = get_settings()
    provider = TracerProvider(
        resource=Resource.create(
            {"service.name": service_name, "deployment.environment": settings.environment}
        )
    )
    if exporter is not None:
        provider.add_span_processor(SimpleSpanProcessor(exporter))
    else:
        endpoint = settings.otel_exporter_endpoint.rstrip("/") + "/v1/traces"
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    _provider = provider
    trace.set_tracer_provider(provider)  # first call wins, later ones only warn

    if instrument:
        _instrument_libraries(provider)
    install_analyzer_hook()


def _instrument_libraries(provider) -> None:
    from opentelemetry.instrumentation.celery import CeleryInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

    from common.db import engine

    # celery injects traceparent into task headers on publish and extracts it on
    # prerun, so api enqueue and worker task share one trace
    CeleryInstrumentor().instrument(tracer_provider=provider)
    RedisInstrumentor().instrument(tracer_provider=provider)
    RequestsInstrumentor().instrument(tracer_provider=provider)
    SQLAlchemyInstrumentor().instrument(engine=engine, tracer_provider=provider)


# ---- analyzer hook ----


@contextmanager
def observe_analyzer(analyzer) -> Iterator[None]:
    start = time.perf_counter()
    outcome = "ok"
    with _get_tracer().start_as_current_span(f"analyzer.{analyzer.name}") as span:
        span.set_attribute("analyzer.name", analyzer.name)
        span.set_attribute("analyzer.keys", list(analyzer.keys))
        span.set_attribute("analyzer.error", False)
        try:
            yield
        except Exception:
            outcome = "error"
            span.set_attribute("analyzer.error", True)
            raise
        finally:
            ANALYZER_DURATION.labels(analyzer.name, outcome).observe(time.perf_counter() - start)


def install_analyzer_hook() -> None:
    # the runner looks `observe` up in its module on every call, so rebinding works
    from common.analytics.analyzers import base

    base.observe = observe_analyzer


# ---- api ----


class MetricsMiddleware:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] == "/metrics":
            await self.app(scope, receive, send)
            return
        start = time.perf_counter()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                # the router stores the matched route on the shared scope
                route = scope.get("route")
                HTTP_DURATION.labels(
                    scope["method"],
                    getattr(route, "path", "unmatched"),
                    str(message["status"]),
                ).observe(time.perf_counter() - start)
            await send(message)

        await self.app(scope, receive, send_wrapper)


def instrument_api(app) -> None:
    """Hook for api/main.py: request histogram, /metrics, and fastapi tracing."""
    if not enabled():
        return
    from fastapi import Response
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    setup_tracing("quantly-api", instrument=False)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=_provider)
    _instrument_libraries(_provider)

    app.add_middleware(MetricsMiddleware)

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        body, content_type = render_metrics()
        return Response(body, media_type=content_type)


# ---- worker ----


def _worker_registry() -> CollectorRegistry:
    # prefork children each hold their own counters, so the parent serves a
    # merged view from PROMETHEUS_MULTIPROC_DIR when it is set
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
    else:
        registry = REGISTRY
    registry.register(QueueDepthCollector())
    return registry


def _on_worker_init(**_: Any) -> None:
    # parent process: serve /metrics for the whole worker
    directory = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if directory:
        shutil.rmtree(directory, ignore_errors=True)
        Path(directory).mkdir(parents=True, exist_ok=True)
    start_http_server(get_settings().metrics_port, registry=_worker_registry())


def _on_worker_process_init(**_: Any) -> None:
    # tracer threads do not survive fork, so each child builds tracing itself
    setup_tracing("quantly-worker")


_job_starts: dict[str, float] = {}


def _on_task_prerun(task_id=None, **_: Any) -> None:
    if task_id:
        _job_starts[task_id] = time.perf_counter()


def _on_task_postrun(task_id=None, task=None, state=None, **_: Any) -> None:
    name = getattr(task, "name", "unknown")
    start = _job_starts.pop(task_id, None)
    if start is not None:
        JOB_DURATION.labels(name).observe(time.perf_counter() - start)
    JOBS.labels(name, (state or "unknown").lower()).inc()


def _on_task_retry(sender=None, **_: Any) -> None:
    JOB_RETRIES.labels(getattr(sender, "name", "unknown")).inc()


def connect_celery_signals() -> None:
    """Hook for worker/celery_app.py. Uses celery signals so tasks.py needs no edits."""
    if not enabled():
        return
    from celery import signals

    signals.worker_init.connect(_on_worker_init, weak=False)
    signals.worker_process_init.connect(_on_worker_process_init, weak=False)
    signals.task_prerun.connect(_on_task_prerun, weak=False)
    signals.task_postrun.connect(_on_task_postrun, weak=False)
    signals.task_retry.connect(_on_task_retry, weak=False)
