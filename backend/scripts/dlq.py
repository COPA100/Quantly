"""inspect and requeue the analysis dead-letter list.

python -m scripts.dlq list
python -m scripts.dlq requeue --all
python -m scripts.dlq requeue --index 0
"""

import argparse
import json
import sys

import redis
from sqlalchemy.orm import Session

from common.models import Job, Portfolio, PortfolioStatus
from common.outbox import enqueue_analysis
from worker.tasks import DLQ_KEY


def list_records(client: redis.Redis) -> list[dict]:
    return [json.loads(raw) for raw in client.lrange(DLQ_KEY, 0, -1)]


def requeue(client: redis.Redis, db: Session, index: int | None = None) -> int:
    # reset the job and portfolio, announce it through the outbox, then drop the
    # record. dropping last means a crash leaves a record to retry, never a loss.
    raws = client.lrange(DLQ_KEY, 0, -1)
    if index is not None:
        raws = raws[index : index + 1]
    requeued = 0
    for raw in raws:
        record = json.loads(raw)
        job = db.get(Job, record["job_id"]) if record.get("job_id") is not None else None
        if job is not None:
            job.status = "queued"
            job.attempts = 0
            job.last_error = None
            job.run_token = None
            job.started_at = None
            job.finished_at = None
            portfolio = db.get(Portfolio, job.portfolio_id)
            if portfolio is not None:
                portfolio.status = PortfolioStatus.PENDING
                portfolio.error_message = None
            enqueue_analysis(db, job)
            requeued += 1
        db.commit()
        client.lrem(DLQ_KEY, 1, raw)
    return requeued


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="print every dead-lettered job")
    again = sub.add_parser("requeue", help="send dead-lettered jobs back to the worker")
    group = again.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true")
    group.add_argument("--index", type=int)
    args = parser.parse_args(argv)

    from common.db import SessionLocal
    from common.redis_client import get_redis

    client = get_redis()
    if args.command == "list":
        records = list_records(client)
        for i, record in enumerate(records):
            print(
                f"{i}\tportfolio={record['portfolio_id']}\tjob={record['job_id']}"
                f"\t{record['failed_at']}\t{record['error_type']}: {record['error']}"
            )
        print(f"{len(records)} dead-lettered", file=sys.stderr)
        return 0

    db = SessionLocal()
    try:
        count = requeue(client, db, None if args.all else args.index)
    finally:
        db.close()
    print(f"requeued {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
