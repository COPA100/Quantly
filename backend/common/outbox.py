import uuid

from sqlalchemy.orm import Session

from common.models import Job, OutboxMessage

ANALYZE_KIND = "analyze_portfolio"

_NAMESPACE = uuid.UUID("6f1c2d4e-9a3b-4c5d-8e7f-0a1b2c3d4e5f")


def task_id_for_job(job_id: int) -> str:
    # one celery task id per job, so every enqueue of a job carries the same id
    return str(uuid.uuid5(_NAMESPACE, f"job:{job_id}"))


def enqueue_analysis(db: Session, job: Job) -> OutboxMessage:
    # job must be flushed. the row commits with the caller's transaction, so the
    # job and its announcement exist together or not at all
    if job.celery_task_id is None:
        job.celery_task_id = task_id_for_job(job.id)
    message = OutboxMessage(
        kind=ANALYZE_KIND,
        payload={
            "portfolio_id": job.portfolio_id,
            "job_id": job.id,
            "task_id": job.celery_task_id,
        },
    )
    db.add(message)
    return message
