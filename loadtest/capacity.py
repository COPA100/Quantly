"""capacity model from k6 burst runs.

reads the json that loadtest/k6.js writes (one file per run) and optional queue
depth samples (csv of seconds,depth), then prints a markdown table with:

  per-worker throughput   jobs finished / drain time / workers, warm vs cold book
  required workers        Little's law: busy = arrival_rate * service_time,
                          workers = ceil(busy / target_utilization)
  backlog per worker      the autoscaling target: jobs one worker can clear
                          inside the wait budget

    python loadtest/capacity.py loadtest/results/burst-*.json --target-rate 5
"""

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Run:
    path: str
    book: str
    workers: int
    jobs: int
    drain_s: float
    mean_latency_s: float | None

    @property
    def throughput(self) -> float:
        # jobs per second for the whole pool
        return self.jobs / self.drain_s

    @property
    def per_worker(self) -> float:
        return self.throughput / self.workers

    @property
    def service_time(self) -> float:
        # worker-seconds one job costs
        return 1 / self.per_worker


def load_run(path: str | Path) -> Run:
    data = json.loads(Path(path).read_text())
    if data.get("scenario") != "burst":
        raise ValueError(f"{path}: only burst runs measure drain time")
    m = data["metrics"]
    jobs = int(m.get("jobs_complete", {}).get("count", 0))
    drain_ms = m.get("completed_at_ms", {}).get("max", 0)
    if jobs == 0 or drain_ms <= 0:
        raise ValueError(f"{path}: no completed jobs recorded")
    latency = m.get("time_to_complete_ms", {}).get("avg")
    return Run(
        path=str(path),
        book=data.get("book", "warm"),
        workers=max(int(data.get("workers", 1)), 1),
        jobs=jobs,
        drain_s=drain_ms / 1000,
        mean_latency_s=None if latency is None else latency / 1000,
    )


def drain_rate_from_samples(samples: list[tuple[float, float]]) -> float | None:
    # jobs per second the pool cleared, from the falling edge after the queue
    # peaks (no arrivals then, so the slope is pure service rate)
    if len(samples) < 3:
        return None
    peak = max(range(len(samples)), key=lambda i: samples[i][1])
    tail = []
    for t, depth in samples[peak:]:
        tail.append((t, depth))
        if depth <= 0:
            break
    if len(tail) < 2 or tail[0][1] <= 0:
        return None
    # least squares slope of depth over time
    n = len(tail)
    mt = sum(t for t, _ in tail) / n
    md = sum(d for _, d in tail) / n
    den = sum((t - mt) ** 2 for t, _ in tail)
    if den == 0:
        return None
    slope = sum((t - mt) * (d - md) for t, d in tail) / den
    return -slope if slope < 0 else None


def read_samples(path: str | Path) -> list[tuple[float, float]]:
    with open(path, newline="") as fh:
        rows = [r for r in csv.reader(fh) if r]
    out = []
    for row in rows:
        try:
            out.append((float(row[0]), float(row[1])))
        except ValueError:
            continue  # header
    return out


def required_workers(rate: float, service_time: float, utilization: float) -> int:
    # Little's law: the mean number of busy workers is rate * service time.
    # dividing by the utilization target leaves headroom for bursts and queueing.
    if not 0 < utilization <= 1:
        raise ValueError("utilization must be in (0, 1]")
    return max(math.ceil(rate * service_time / utilization), 1)


def backlog_target(per_worker: float, wait_budget_s: float) -> float:
    # a job joining a queue of b jobs per worker waits about b / per_worker
    return per_worker * wait_budget_s


def render(
    runs: list[Run],
    target_rate: float,
    utilization: float,
    wait_budget_s: float,
    samples_rate: float | None = None,
) -> str:
    lines = [
        "| book | workers | jobs | drain (s) | jobs/s/worker | service time (s) "
        "| mean latency (s) |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in sorted(runs, key=lambda r: (r.book, r.workers)):
        lat = "n/a" if r.mean_latency_s is None else f"{r.mean_latency_s:.1f}"
        lines.append(
            f"| {r.book} | {r.workers} | {r.jobs} | {r.drain_s:.1f} | {r.per_worker:.3f} "
            f"| {r.service_time:.2f} | {lat} |"
        )
    lines += [
        "",
        f"Sizing for {target_rate:g} uploads/s at {utilization:.0%} utilization:",
        "",
        "| book | workers needed | backlog per worker target |",
        "|---|---|---|",
    ]
    for book in sorted({r.book for r in runs}):
        # average over runs of the same book, the per-worker rate should not
        # depend on the pool size if the pool is cpu bound
        group = [r for r in runs if r.book == book]
        per_worker = sum(r.per_worker for r in group) / len(group)
        need = required_workers(target_rate, 1 / per_worker, utilization)
        lines.append(f"| {book} | {need} | {backlog_target(per_worker, wait_budget_s):.1f} |")
    if samples_rate is not None:
        lines += [
            "",
            f"Queue depth samples imply a pool drain rate of {samples_rate:.2f} jobs/s.",
        ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("results", nargs="+", help="k6 burst json files")
    p.add_argument("--queue-samples", help="csv of seconds,depth from the burst run")
    p.add_argument("--target-rate", type=float, default=5.0, help="uploads per second to size for")
    p.add_argument("--utilization", type=float, default=0.7)
    p.add_argument("--wait-budget", type=float, default=30.0, help="queue wait budget in seconds")
    p.add_argument("--out", help="write the markdown here instead of stdout")
    args = p.parse_args(argv)

    runs = [load_run(path) for path in args.results]
    rate = None
    if args.queue_samples:
        rate = drain_rate_from_samples(read_samples(args.queue_samples))
    text = render(runs, args.target_rate, args.utilization, args.wait_budget, rate)
    if args.out:
        Path(args.out).write_text(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
