# Capacity model

How many workers a given upload rate needs, and what the autoscaler should hold the queue at.

## Status of the numbers

**This document has no measured results yet.** The load tests (`loadtest/`, `make loadtest`) need Docker, and Docker was not available on the machine this was written on, so nothing was run. Every table below is empty and marked. Fill them by running the tests and `loadtest/capacity.py`, and record the hardware next to them. No figure here is an estimate or a guess.

## Model

The work is a queue with parallel servers: uploads arrive at rate `lambda` (jobs/s), each worker serves jobs at rate `mu` (jobs/s per worker).

1. **Per-worker throughput.** Measured with the burst scenario: `BURST_UPLOADS` jobs are enqueued at once, and the time until the last one completes is the drain time `T`. With `W` workers, `mu = jobs / T / W`. Service time is `S = 1 / mu` worker-seconds per job. Because the burst keeps every worker busy until the queue empties, `T` is a throughput measurement, not a latency one. (`T` includes the few seconds it takes to send the burst and the outbox relay interval, so it slightly understates `mu` for small bursts. Use enough jobs that this is noise.)
2. **Warm and cold.** The worker caches analytics by holdings and as-of date, and price history in the shared `prices` table. A warm run (`BOOK=warm`) re-uploads one book, so after the first job nearly everything is cached. A cold run (`BOOK=cold`) uses a different book per upload over a pool of tickers and starts from an empty database. Size for cold: warm is the best case, and real users bring new books.
3. **Little's law.** The mean number of busy workers is `L = lambda * S`. To keep utilization at a target `rho` (for example 0.7, so bursts and variance have room), the pool needs `W = ceil(lambda * S / rho)` workers. At `rho = 1` the queue grows without bound under any variability, which is why the target is below 1.
4. **Backlog per worker.** A job that joins a queue holding `b` jobs per worker waits about `b / mu` seconds. So a wait budget `D` gives a target of `b = mu * D` queued jobs per running worker. That `b` is the value for `worker_backlog_target` in Terraform. Holding the backlog there means each job waits about `D` before a worker takes it.

`loadtest/capacity.py` does steps 1 to 4 from the k6 results.

## Why backlog per worker and not CPU

A worker consuming a queue is either busy or waiting for work. Its CPU says whether it is busy, not how many jobs are waiting, so a queue of 1,000 jobs and a queue of 3 jobs look identical (all workers at 100%). CPU also lags: it rises only after workers already have work. Backlog per worker is a direct measure of the thing the user feels, queue wait, and it scales in proportion: if the backlog per worker is twice the target, the pool is half the size it needs. That proportionality is what target tracking uses, `desired = ceil(running * backlog_per_worker / target)`. For the api, which is stateless and request-driven, CPU and request count per target are the right signals, and are what the Terraform uses there.

## Measured results

Hardware: _not recorded, run `make loadtest` and fill in cpu model, cores, ram, docker engine._

Per-worker throughput (burst scenario, `capacity.py` output):

| book | workers | jobs | drain (s) | jobs/s/worker | service time (s) | mean latency (s) |
|---|---|---|---|---|---|---|
| warm | | | | run `make loadtest` to fill in | | |
| cold | | | | run `make loadtest` to fill in | | |

Workers needed (Little's law, utilization target 70%):

| target uploads/s | book | workers needed | backlog per worker target (30 s wait budget) |
|---|---|---|---|
| | warm | run `make loadtest` to fill in | |
| | cold | run `make loadtest` to fill in | |

Single-node limits (steady and ramp scenarios):

| measure | value |
|---|---|
| upload p50 / p95 / p99 at steady rate | run `make loadtest` to fill in |
| highest upload rate before p99 > 300 ms or errors > 0.1% (ramp) | run `make loadtest` to fill in |
| bottleneck at that rate (api cpu, postgres, redis, worker) | run `make loadtest` to fill in |

## Using the numbers

1. `SCENARIO=burst BOOK=cold WORKERS=1 make loadtest`, then again with `BOOK=warm` and with more workers. Check that `jobs/s/worker` stays flat as workers grow. If it falls, something shared (postgres, redis) is the limit and adding workers will not help.
2. `python loadtest/capacity.py loadtest/results/burst-*.json --target-rate <uploads/s> --utilization 0.7 --wait-budget 30`.
3. Put the backlog target in `worker_backlog_target` and the worker count (with headroom) in `worker_max_count`.
4. Check the policy against a real queue depth series with `python loadtest/simulate_scaling.py depth.csv --target <b>`. The replay is open loop: it shows what the policy would request for that depth, not how the queue would have drained with the extra workers.

## Limits of the model

- It assumes jobs cost about the same. Cold jobs with many new tickers cost more than warm ones, so use the cold number when in doubt.
- The local runs use pinned container CPU limits, not Fargate. Re-measure on the target task size (`worker_cpu`/`worker_memory`) before trusting the worker count for AWS, since a Fargate vCPU and a docker CPU limit on a laptop are not the same speed.
- Postgres and Redis are single nodes. If throughput per worker stops being flat, the model above no longer holds and the shared service is the bottleneck.
- Workers start in tens of seconds on Fargate. The burst drain time here does not include that, and the simulator takes it as `--start-s`.
