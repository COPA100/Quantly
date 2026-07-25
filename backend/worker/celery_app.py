from celery import Celery

from common.config import get_settings

settings = get_settings()

# the tasks module is imported lazily by the worker via `include`, so the api can
# import this app to enqueue by name without pulling in pandas/yfinance.
celery_app = Celery(
    "quantly",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["worker.tasks"],
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
)
