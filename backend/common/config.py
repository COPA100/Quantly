from datetime import date
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration, loaded from environment variables (QUANTLY_*) or a local .env file."""

    model_config = SettingsConfigDict(env_prefix="QUANTLY_", env_file=".env", extra="ignore")

    app_name: str = "Quantly"
    environment: str = "dev"
    cors_origins: list[str] = ["http://localhost:5173"]
    # default matches the docker-compose postgres service
    database_url: str = "postgresql+psycopg://quantly:quantly@localhost:5432/quantly"

    # object storage. defaults point at the local s3 stand-in in docker-compose,
    # which accepts any credentials. in prod, unset the endpoint url and let the
    # iam role supply credentials.
    s3_bucket: str = "quantly-portfolios"
    s3_region: str = "us-east-1"
    s3_endpoint_url: str | None = "http://localhost:9000"
    aws_access_key_id: str | None = "local-dev"
    aws_secret_access_key: str | None = "local-dev"

    # reject uploads larger than this many bytes
    max_upload_bytes: int = 5_000_000

    # redis. db 0 is the current-price cache, celery gets its own dbs below so
    # broker/result keys never collide with cached prices.
    redis_url: str = "redis://localhost:6379/0"
    current_price_ttl_seconds: int = 900  # 15 min

    # celery broker (queued tasks) and result backend (task state/return values)
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # server-sent status stream. the heartbeat stays well under the alb idle
    # timeout (60s); the cap bounds how long one request can hold a connection.
    sse_heartbeat_seconds: float = 15
    sse_max_seconds: float = 600

    # computed analytics cached by holdings+as-of hash. one day, since a given
    # book's metrics only change when prices roll over to the next day.
    analytics_cache_ttl_seconds: int = 86400

    # daily history is fetched back to this date for every ticker (or its
    # listing, if later). deep history feeds stress tests of past crises.
    history_start: date = date(2007, 1, 1)
    # metrics are computed over this trailing window of the stored history
    analysis_window_years: int = 5

    # threads per c++ kernel call. the worker already runs one process per core,
    # so 1 avoids oversubscribing; raise it for a single-process deployment.
    engine_threads: int = 1

    # market benchmark used for beta, just another shared ticker
    benchmark_ticker: str = "SPY"

    # auth. the secret MUST be overridden in prod via QUANTLY_JWT_SECRET.
    jwt_secret: str = "dev-insecure-secret-change-in-prod"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # worker reliability. the lock ttl is renewed by a heartbeat, so it only has
    # to outlive a few missed beats after a crash.
    analysis_lock_ttl_seconds: float = 30
    task_max_attempts: int = 4
    retry_base_seconds: float = 2
    retry_cap_seconds: float = 60
    # redis redelivers an unacked task after this long. keep it above the
    # longest retry backoff or a waiting retry gets delivered twice.
    broker_visibility_timeout_seconds: int = 300

    # outbox relay and the sweeper for portfolios stuck in pending/processing
    outbox_relay_interval_seconds: float = 2
    outbox_batch_size: int = 50
    sweeper_interval_seconds: float = 60
    stuck_after_seconds: int = 900

    # sliding-window rate limits: max requests per window, per user (upload)
    # or per client ip (login)
    rate_limit_enabled: bool = True
    rate_limit_upload_max: int = 10
    rate_limit_upload_window_seconds: int = 60
    rate_limit_login_max: int = 10
    rate_limit_login_window_seconds: int = 60
    # short timeouts so a dead redis fails fast instead of hanging requests
    redis_socket_timeout_seconds: float = 2
    # observability. everything in common/telemetry.py is a no-op unless enabled.
    otel_enabled: bool = False
    otel_exporter_endpoint: str = "http://localhost:4318"  # otlp/http base url
    metrics_port: int = 9100  # worker prometheus exporter
    celery_queue_name: str = "celery"  # list whose length is the queue depth

    # google sign-in. the client id is the audience the id token must match.
    google_client_id: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
