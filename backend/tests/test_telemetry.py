import pytest
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient
from opentelemetry import propagate, trace
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from common import telemetry
from common.analytics.analyzers import base
from common.analytics.analyzers.base import Analyzer, run_analyzers
from common.config import get_settings


@pytest.fixture
def otel_on(monkeypatch):
    monkeypatch.setenv("QUANTLY_OTEL_ENABLED", "true")
    get_settings.cache_clear()
    original = base.observe
    yield
    base.observe = original
    get_settings.cache_clear()


@pytest.fixture
def spans(otel_on):
    exporter = InMemorySpanExporter()
    telemetry.setup_tracing("test", exporter=exporter, instrument=False)
    return exporter


def _sample(metric: str, **labels) -> float:
    return telemetry.REGISTRY.get_sample_value(metric, labels) or 0.0


def test_disabled_by_default_is_a_noop():
    assert telemetry.enabled() is False
    before = base.observe
    provider_before = telemetry._provider
    telemetry.setup_tracing("x")
    telemetry.connect_celery_signals()
    hits = _sample("quantly_cache_requests_total", cache="analytics", result="hit")
    telemetry.record_cache(True)
    assert _sample("quantly_cache_requests_total", cache="analytics", result="hit") == hits
    assert base.observe is before
    assert telemetry._provider is provider_before

    app = FastAPI()
    telemetry.instrument_api(app)
    assert TestClient(app).get("/metrics").status_code == 404


def test_observe_hook_records_span_and_metric_per_analyzer(spans):
    good = Analyzer("good", ("a",), lambda ctx: {"a": 1})
    bad = Analyzer("bad", ("b", "c"), lambda ctx: 1 / 0)
    ctx = type("Ctx", (), {"results": {}})()

    ok_count = "quantly_analyzer_duration_seconds_count"
    before_ok = _sample(ok_count, analyzer="good", outcome="ok")
    before_err = _sample(ok_count, analyzer="bad", outcome="error")
    run_analyzers(ctx, [good, bad])

    by_name = {s.name: s for s in spans.get_finished_spans()}
    assert by_name["analyzer.good"].attributes["analyzer.error"] is False
    assert by_name["analyzer.good"].attributes["analyzer.name"] == "good"
    assert by_name["analyzer.bad"].attributes["analyzer.error"] is True
    assert tuple(by_name["analyzer.bad"].attributes["analyzer.keys"]) == ("b", "c")
    assert _sample(ok_count, analyzer="good", outcome="ok") == before_ok + 1
    assert _sample(ok_count, analyzer="bad", outcome="error") == before_err + 1


def test_cache_counter_when_enabled(otel_on):
    before = _sample("quantly_cache_requests_total", cache="analytics", result="hit")
    telemetry.record_cache(True)
    assert _sample("quantly_cache_requests_total", cache="analytics", result="hit") == before + 1


def test_metrics_endpoint_exposes_request_histogram():
    app = FastAPI()

    @app.get("/items/{item_id}")
    def item(item_id: int):
        return {"id": item_id}

    @app.get("/metrics")
    def metrics():
        body, content_type = telemetry.render_metrics()
        return Response(body, media_type=content_type)

    app.add_middleware(telemetry.MetricsMiddleware)
    client = TestClient(app)
    client.get("/items/7")
    text = client.get("/metrics").text
    assert "quantly_http_request_duration_seconds_bucket" in text
    assert 'route="/items/{item_id}"' in text
    assert 'status="200"' in text


def test_instrument_api_mounts_metrics_route(otel_on, monkeypatch):
    # keep the real otlp exporter out of the test
    monkeypatch.setattr(
        "opentelemetry.sdk.trace.export.BatchSpanProcessor",
        lambda _exporter: SimpleSpanProcessor(InMemorySpanExporter()),
    )
    app = FastAPI()
    telemetry.instrument_api(app)
    try:
        response = TestClient(app).get("/metrics")
        assert response.status_code == 200
        assert "quantly_http_request_duration_seconds" in response.text
    finally:
        for instrumentor in (
            CeleryInstrumentor,
            RedisInstrumentor,
            RequestsInstrumentor,
            SQLAlchemyInstrumentor,
        ):
            instrumentor().uninstrument()


def test_trace_context_propagates_through_celery_headers():
    from celery import Celery

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    app = Celery("t", broker="memory://", backend="cache+memory://")
    CeleryInstrumentor().instrument(tracer_provider=provider)
    try:
        tracer = provider.get_tracer("test")
        with tracer.start_as_current_span("api.enqueue") as parent:
            app.send_task("analyze_portfolio", args=[1])
            parent_trace = parent.get_span_context().trace_id

        with app.connection_for_read() as conn:
            queue = conn.SimpleQueue("celery")
            message = queue.get(timeout=2)
            headers = message.headers
            message.ack()
            queue.close()

        assert "traceparent" in headers
        remote = trace.get_current_span(propagate.extract(headers)).get_span_context()
        assert remote.trace_id == parent_trace
        child = [s for s in exporter.get_finished_spans() if s.name != "api.enqueue"]
        assert child and {s.context.trace_id for s in child} == {parent_trace}
    finally:
        CeleryInstrumentor().uninstrument()
