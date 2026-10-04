"""replay a queue depth series through the worker target-tracking policy.

the math mirrors the aws policy in infra/autoscaling.tf: the metric is backlog per
worker (queue depth / running workers), the target is a number of jobs per worker,
and desired = ceil(running * metric / target), clamped to min/max. scale out acts
at once, scale in waits for several quiet samples and a cooldown, as aws does.

this is an open-loop replay: the depth series is taken as given, it does not
shrink because the simulated pool grew. it shows what the policy would ask for,
not how the queue would have drained.

    python loadtest/simulate_scaling.py depth.csv --target 20 --max 10
    python loadtest/simulate_scaling.py --synthetic        # a made-up burst
"""

import argparse
import csv
import math
from dataclasses import dataclass


def backlog_per_worker(depth: float, running: int) -> float:
    # same denominator rule as the lambda: never divide by zero workers
    return depth / max(running, 1)


def desired_replicas(running: int, metric: float, target: float, lo: int, hi: int) -> int:
    # target tracking: scale the pool so metric returns to the target. from zero
    # the ratio uses one worker, otherwise 0 * anything stays 0.
    want = math.ceil(max(running, 1) * metric / target)
    return min(max(want, lo), hi)


@dataclass
class Policy:
    target: float
    min_replicas: int = 0
    max_replicas: int = 10
    scale_in_cooldown_s: float = 300
    scale_out_cooldown_s: float = 60
    # consecutive samples under target before scale in is allowed
    scale_in_samples: int = 3
    start_s: float = 60  # seconds for a requested task to start running


@dataclass
class Row:
    t: float
    depth: float
    running: int
    desired: int
    metric: float


def simulate(series: list[tuple[float, float]], policy: Policy, initial: int = 0) -> list[Row]:
    running = initial
    pending: list[tuple[float, int]] = []  # (ready_at, replica count it brings the pool to)
    last_out = last_in = -math.inf
    quiet = 0
    rows = []
    for t, depth in series:
        # tasks that finished starting
        for ready_at, count in list(pending):
            if ready_at <= t:
                running = count
                pending.remove((ready_at, count))
        metric = backlog_per_worker(depth, running)
        want = desired_replicas(
            running, metric, policy.target, policy.min_replicas, policy.max_replicas
        )
        quiet = quiet + 1 if metric < policy.target else 0
        target_count = running
        if want > running and t - last_out >= policy.scale_out_cooldown_s:
            target_count = want
            last_out = t
        elif want < running and quiet >= policy.scale_in_samples:
            if t - last_in >= policy.scale_in_cooldown_s:
                target_count = want
                last_in = t
        if target_count > running:
            pending.append((t + policy.start_s, target_count))
        elif target_count < running:
            running = target_count  # stopping a task is quick
            pending = []
        rows.append(Row(t, depth, running, target_count, metric))
    return rows


def synthetic_burst(step_s: float = 60, minutes: int = 40) -> list[tuple[float, float]]:
    # idle, a spike to 400 jobs, then a slow tail: just to exercise the policy
    shape = [0] * 3 + [400, 380, 340, 300, 240, 180, 120, 80, 50, 30, 15, 5] + [0] * 25
    return [(i * step_s, float(d)) for i, d in enumerate(shape[:minutes])]


def read_series(path: str) -> list[tuple[float, float]]:
    out = []
    with open(path, newline="") as fh:
        for row in csv.reader(fh):
            try:
                out.append((float(row[0]), float(row[1])))
            except (ValueError, IndexError):
                continue
    return out


def render(rows: list[Row]) -> str:
    lines = ["t(s)  depth  backlog/worker  running  desired"]
    for r in rows:
        lines.append(
            f"{r.t:>5.0f} {r.depth:>6.0f} {r.metric:>15.1f} {r.running:>8d} {r.desired:>8d}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("series", nargs="?", help="csv of seconds,depth")
    p.add_argument("--synthetic", action="store_true")
    p.add_argument("--target", type=float, default=20.0, help="backlog per worker target")
    p.add_argument("--min", type=int, default=0, dest="min_replicas")
    p.add_argument("--max", type=int, default=10, dest="max_replicas")
    p.add_argument("--start-s", type=float, default=60.0)
    p.add_argument("--initial", type=int, default=0)
    args = p.parse_args(argv)
    if not args.series and not args.synthetic:
        p.error("give a csv or --synthetic")
    series = synthetic_burst() if args.synthetic else read_series(args.series)
    policy = Policy(
        target=args.target,
        min_replicas=args.min_replicas,
        max_replicas=args.max_replicas,
        start_s=args.start_s,
    )
    print(render(simulate(series, policy, args.initial)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
