from celery import Celery

from common.config import get_settings
from common.telemetry import connect_celery_signals

settings = get_settings()

# the tasks module is imported lazily by the worker via `include`, so the api can
# import this app to enqueue by name without pulling in pandas/yfinance.
celery_app = Celery(
    "quantly",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["worker.tasks", "worker.outbox"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # keep a task tied to one portfolio, so a lost worker requeues cleanly
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # finished task state expires after a day, the Job row is the durable record
    result_expires=86400,
    # an unacked task goes back on the queue after this long, which is how a
    # killed worker's task is redelivered
    broker_transport_options={"visibility_timeout": settings.broker_visibility_timeout_seconds},
    # run by the `beat` service, one instance only
    beat_schedule={
        "relay-outbox": {
            "task": "relay_outbox",
            "schedule": settings.outbox_relay_interval_seconds,
        },
        "sweep-stuck-portfolios": {
            "task": "sweep_stuck_portfolios",
            "schedule": settings.sweeper_interval_seconds,
        },
    },
)

connect_celery_signals()
