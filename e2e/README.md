# End-to-end tests

Playwright drives the real stack: register, upload `example_csv/ex1.csv`, wait for the
worker to finish, and check the overview, risk and correlation sections render.

## Market data

The app has no mock market-data source yet, and CI must not hit Yahoo. So the run seeds
synthetic daily prices for the sample book and the benchmark straight into Postgres,
plus current prices in Redis (`seed_market.py`). With those in place the worker finds
every series up to date and makes no Yahoo calls. When a `mock` market-data source is
added to the app, replace the seed step with that setting.

## Run it locally

```bash
docker compose up -d postgres redis s3
cd backend
alembic upgrade head
PYTHONPATH=. python ../e2e/seed_market.py
docker compose up -d --build worker beat   # from the repo root
uvicorn api.main:app --port 8000        # leave running

cd e2e
npm ci
npx playwright install chromium
npx playwright test
```

Playwright starts the Vite dev server on 5173. Set `E2E_BASE_URL` to test an already
running frontend instead.
