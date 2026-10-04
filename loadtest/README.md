# Load tests

k6 scripts and tooling for finding how much one api and one worker can take, and how many workers a given upload rate needs. Nothing here has numbers baked in: results land in `loadtest/results/` (git-ignored) and `docs/capacity.md` holds only what was measured.

## What is here

| File | Purpose |
|---|---|
| `k6.js` | the load test, three scenarios selected with `SCENARIO` |
| `docker-compose.loadtest.yml` | override that pins cpu/mem, adds an api container, mock market data, high rate limits |
| `capacity.py` | turns burst results into per-worker throughput and a worker count |
| `simulate_scaling.py` | replays a queue depth series through the autoscaling policy math |

## Scenarios

- `steady`: constant arrival rate of uploads (`RATE`/s) plus reads of the portfolio, status and analytics endpoints (`READ_RATIO` reads per upload) for `DURATION`.
- `ramp`: ramping arrival rate from `RAMP_START` to `RAMP_PEAK` uploads/s over `RAMP_DURATION`. It aborts when the upload p99 passes 300 ms or the error rate passes 0.1%, so the last rate before the abort is the limit.
- `burst`: `BURST_UPLOADS` uploads as fast as `100` VUs can send them, each polling `GET /portfolios/{id}/status` until the job is complete. `completed_at_ms` max is the time to drain the queue. This is the run `capacity.py` needs.

Thresholds come from `docs/slo.md`: upload accept p99 under 300 ms, error rate under 0.1% (the 99.9% availability SLO). A failed threshold makes k6 exit non-zero.

## Run it

```bash
# 1. the stack, with 2 worker replicas (from the repo root)
docker compose -f docker-compose.yml -f loadtest/docker-compose.loadtest.yml \
  up -d --build --scale worker=2 postgres redis s3 api worker beat

# 2. a scenario, using the k6 docker image so nothing is installed locally
docker run --rm -i --network host -v "$PWD":/work -w /work \
  -e SCENARIO=burst -e BURST_UPLOADS=200 -e WORKERS=2 -e BOOK=warm \
  grafana/k6 run /work/loadtest/k6.js
```

`make loadtest` does both and prints the capacity table (`SCENARIO=ramp WORKERS=4 make loadtest` to change it). On Docker Desktop for Windows or Mac, `--network host` does not reach the host, so use `-e BASE_URL=http://host.docker.internal:8000` instead.

Results are written to `loadtest/results/<scenario>.json`. Rename or set `SUMMARY_PATH` to keep several (for example `burst-warm-2w.json`).

## Settings

Set on the k6 side with `-e`:

| Variable | Default | Meaning |
|---|---|---|
| `BASE_URL` | `http://localhost:8000` | api address |
| `SCENARIO` | `steady` | `steady`, `ramp`, `burst` |
| `USERS` | `20` | users registered and logged in during setup |
| `BOOK` | `warm` | `warm`: every upload is the sample book. `cold`: unique books over a ticker pool |
| `TICKER_POOL`, `BOOK_SIZE` | `200`, `8` | size of the cold ticker pool and holdings per book |
| `WORKERS` | `1` | worker replicas, recorded in the result for `capacity.py` |
| `RATE`, `DURATION`, `READ_RATIO` | `5`, `2m`, `4` | steady scenario |
| `RAMP_START`, `RAMP_PEAK`, `RAMP_DURATION` | `2`, `60`, `5m` | ramp scenario |
| `BURST_UPLOADS`, `POLL_INTERVAL`, `DRAIN_TIMEOUT_S` | `200`, `1`, `900` | burst scenario |
| `LOGIN_PAUSE` | `0` | seconds to sleep between setup logins, if the login limit is not raised |

### Rate limits

Uploads are limited per user and logins per client ip (sliding window, 10 per minute each by default). A load run needs to get past that, so the compose override sets `QUANTLY_RATE_LIMIT_UPLOAD_MAX` and `QUANTLY_RATE_LIMIT_LOGIN_MAX` to 1,000,000. Override them on the compose command line if you want to test with the limiter on. If you run the api some other way, set the same two variables high, or setup fails at login (429) and the run aborts with a message saying so. Do not do this on a deployed environment.

Access tokens are issued once in setup. The override raises their lifetime to 120 minutes, so keep runs under that.

### Warm and cold

The worker caches analytics by holdings and as-of date, and market history in the shared prices table. `BOOK=warm` re-uploads one book, so after the first job nearly everything hits a cache: that is the best case. `BOOK=cold` uploads a different book each time over a pool of synthetic tickers, so analytics are always recomputed and the first sight of each ticker generates its history. For a fully cold number also start from an empty database (`docker compose down -v`). Run both and keep both.

## Hardware assumptions

The override pins limits per container, so the numbers describe those limits, not the host. Pinned values:

| Service | CPU | Memory |
|---|---|---|
| api (2 uvicorn workers, `API_WORKERS`) | 2 | 1 GB |
| worker (each replica, celery concurrency 2, `WORKER_CONCURRENCY`) | 2 | 2 GB |
| postgres (fsync off) | 2 | 2 GB |
| redis | 1 | 512 MB |
| s3mock | 1 | 1 GB |
| beat | 0.5 | 256 MB |

With `--scale worker=N` the stack asks for about `7.5 + 2N` cpus. If the host has fewer, the containers contend and results are only valid for that host: write the cpu model and core count next to any number you publish. k6 itself runs on the same machine here, so keep its load modest (it is light for these rates, but a 500 VU ramp is not free). Record: cpu model, cores, ram, docker engine and whether it runs under WSL2 or a VM.

## Capacity and scaling tools

```bash
python loadtest/capacity.py loadtest/results/burst-*.json --target-rate 5 --utilization 0.7
python loadtest/simulate_scaling.py --synthetic --target 20 --max 10
python loadtest/simulate_scaling.py depth.csv --target 20      # csv of seconds,depth
```

`capacity.py` takes burst runs only, with `--queue-samples depth.csv` as an optional cross-check of the drain rate. The model is described in `docs/capacity.md`.
