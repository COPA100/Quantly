# Development

Running Quantly locally, the test suites and CI, observability, and load testing.

## Getting started

Everything runs locally for free. You need Docker, Python 3.13+ and a current Node LTS.

```bash
# postgres, redis, s3mock (a local stand-in for s3), the celery worker and beat
docker compose up -d

# api
cd backend
python -m venv .venv
# Windows (PowerShell):   .venv\Scripts\Activate.ps1
# macOS / Linux:          source .venv/bin/activate
pip install -r requirements/dev.txt
alembic upgrade head
uvicorn api.main:app --reload      # http://localhost:8000, docs at /docs
```

In a second terminal:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev                        # http://localhost:5173
```

Then either register and upload one of the files in [`example_csv/`](../example_csv), or create a ready-made demo account with an analyzed portfolio:

```bash
cd backend
python -m scripts.seed             # prints the demo login when it is done
```

The worker container compiles the C++ engine into its image. Outside the container the engine is optional, and without it the same code uses the NumPy implementations. To build and install it into the current environment (needs a C++ compiler and CMake):

```bash
pip install ./engine
```

## Tests and CI

```bash
make lint     # ruff, isort, black
make test     # pytest
cd frontend && npm test   # vitest
cd backend && HYPOTHESIS_PROFILE=ci pytest tests/property   # property tests, see tests/property/README.md
```

| Workflow | Runs on | Does |
|---|---|---|
| `lint`, `test` | every push and PR | ruff, isort, black, pytest (including the Hypothesis property tests on a fixed seed). The job summary shows a coverage table and the XML is uploaded as an artifact |
| `engine` | every push and PR | builds the C++ engine, runs its Catch2 tests, then pytest with the engine installed so the Python/C++ parity tests run |
| `images` | PRs touching `backend/` | builds the api and worker images |
| `frontend` | every push and PR | oxlint, type-check and build, vitest |
| `sanitizers` | PRs and pushes touching `engine/` | builds the engine tests with AddressSanitizer and UBSan (`-DQUANTLY_SANITIZE=ON`) and runs them |
| `fuzz` | PRs touching the CSV parser or engine, weekly, on demand | Atheris on `parse_portfolio` (only `CSVValidationError` may escape) and a libFuzzer harness over the drawdown, correlation and VaR kernels. 60s per target on PRs, 10 minutes weekly. Crashing inputs are uploaded |
| `e2e` | pushes to `main`, PRs touching app code | Playwright against docker compose: register, upload `ex1.csv`, wait for the analysis, check the sections render. Prices are seeded, no Yahoo calls ([details](../e2e/README.md)) |
| `terraform plan` | PRs touching `infra/` | fmt, validate, and a plan posted as a PR comment |
| `deploy` | push to `main`, while enabled | pushes images to ECR, `terraform apply`, migrations, smoke test |

## Observability

Tracing and metrics are off by default and cost nothing when off. To turn them on locally:

```bash
# worker, collector, jaeger, prometheus and grafana
QUANTLY_OTEL_ENABLED=true docker compose --profile obs up -d

# api on the host, exporting to the collector
cd backend
QUANTLY_OTEL_ENABLED=true uvicorn api.main:app
```

| What | Where |
|---|---|
| Grafana dashboard (no login) | http://localhost:3000 |
| Traces (Jaeger) | http://localhost:16686 |
| Prometheus, rules and alerts | http://localhost:9090 |
| API metrics | http://localhost:8000/metrics |
| Worker metrics | http://localhost:9100 |

The dashboard shows request rate, p50/p95/p99 latency, 5xx ratio, job duration, a per-analyzer breakdown, queue depth, retries and failures, cache hit ratio and SLO burn rates. An upload shows up in Jaeger as one trace from the API request through the queue to the worker task and each analyzer. SLOs and the burn-rate alert rules are in [`docs/slo.md`](./slo.md).

## Load testing and scaling

[`loadtest/`](../loadtest) has a k6 test with three scenarios (steady, ramp until it breaks, upload burst) and a compose override that pins CPU and memory for each service and runs the api in a container. Market data comes from a deterministic synthetic source (`QUANTLY_MARKET_DATA_SOURCE=mock`) so runs do not touch Yahoo and are repeatable. The thresholds are the ones in [`docs/slo.md`](./slo.md).

```bash
SCENARIO=burst WORKERS=2 BOOK=cold make loadtest   # needs docker, k6 runs from its image
```

`loadtest/capacity.py` turns the burst results into per-worker throughput and a worker count (Little's law), and `loadtest/simulate_scaling.py` replays a queue depth series through the autoscaling policy. The model and every measured number are in [`docs/capacity.md`](./capacity.md).

In AWS, workers scale on backlog per worker (queue depth divided by running workers), published by a small Lambda, and the api scales on request count and CPU. See `infra/README.md`. The configuration passes `terraform fmt` and `validate`; it has not been applied.
