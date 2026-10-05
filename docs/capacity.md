# Capacity model

How many workers a given upload rate needs, and what the autoscaler should hold the queue at.

## Status of the numbers

Measured on 2026-10-05 with the k6 scenarios in `loadtest/` against the pinned compose stack, using the mock market data source. Hardware and limits are listed with the results. Everything below was run, nothing is estimated.

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

Hardware: Intel Core Ultra 9 185H laptop (22 logical CPUs, 32 GB RAM), Docker Desktop 29.6 on WSL2 (22 CPUs, 15.4 GB to Docker). Container limits from `loadtest/docker-compose.loadtest.yml`: api 1 CPU / 1 GB (uvicorn, one process), each worker 2 CPUs / 2 GB with Celery concurrency 2, postgres 2 CPUs / 2 GB, redis 1 CPU / 512 MB. Market data from the mock source, so no network time is included.

### Single api node (steady and ramp)

| measure | value |
|---|---|
| steady 5 uploads/s + 20 reads/s, 2 min | upload p50 / p95 / p99 34 / 87 / 113 ms, 0 errors |
| steady 10 uploads/s + 40 reads/s, 1 min | upload p99 55 ms, 0 errors |
| steady 20 uploads/s + 80 reads/s, 1 min | upload p99 51 ms, 0 errors, 93.6 req/s served |
| steady 30 uploads/s + 120 reads/s, 1 min | throughput capped at 97 req/s, 2.1% errors, SLO broken |
| ramp to the first SLO break | about 100 req/s (20 uploads/s with reads) |
| bottleneck | api CPU (one uvicorn process on 1 CPU). Postgres stayed near 20% CPU |

Past the knee, requests queue behind the api's thread pool. When every database connection is taken for longer than the pool timeout, the api now answers 503 with `Retry-After` instead of a 500, so overload reads as overload. In a 200-upload burst from 100 concurrent clients, 24 uploads were shed this way and none failed otherwise.

### Worker throughput (burst of 200 unique books, `BOOK=cold`)

Two cases. A fresh stack has an empty `prices` table, so every job also loads up to 20 years of history for its new tickers. Stored prices is the same burst once those tickers are in the table, which is the steady state for a service whose users mostly hold common tickers.

| case | workers | jobs | drain (s) | jobs/s total | jobs/s/worker | service time (s) |
|---|---|---|---|---|---|---|
| fresh stack | 1 | 190 | 293.5 | 0.65 | 0.647 | 1.54 |
| fresh stack | 2 | 180 | 164.2 | 1.10 | 0.548 | 1.82 |
| fresh stack | 4 | 176 | 122.0 | 1.44 | 0.361 | 2.77 |
| stored prices | 1 | 200 | 94.5 | 2.12 | 2.117 | 0.47 |
| stored prices | 2 | 199 | 51.1 | 3.89 | 1.948 | 0.51 |
| stored prices | 4 | 200 | 32.3 | 6.19 | 1.550 | 0.65 |

(Jobs under 200 are uploads the api shed with a 503 during the burst; every accepted job completed.)

What this says:

- With prices stored, adding workers scales well: 2 workers give 92% of linear, 4 give 73%. The falloff at 4 is shared contention (postgres, the machine's own cores).
- On a fresh stack, throughput per worker falls as workers are added. That is the signature of a shared bottleneck: the first job to see a ticker writes about 5,000 price rows into one table, and those writes, not the analysis, dominate. A cold start costs about 3x a warm one.
- So the cheapest capacity win is not more workers but prefetching history for common tickers ahead of time (a nightly job), which turns most cold jobs into stored-price jobs.

### Workers needed (Little's law, 70% utilization, 30 s wait budget)

| target uploads/s | case | workers needed | backlog per worker target |
|---|---|---|---|
| 5 | fresh stack (worst case) | 14 | 15.6 |
| 5 | stored prices | 4 | 56.1 |

The stored-prices numbers are the ones to size from once the price table is warm; the fresh-stack row is the bound for a cold start. These are laptop containers, not Fargate vCPUs, so re-measure on the real task size before trusting the counts in AWS.

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
