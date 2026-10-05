# Quantly design

Status: implemented. Author: Colin Park.

## Context

Brokerage screens tell you what a portfolio is worth and not much else. Quantly takes a brokerage CSV export and answers the questions a risk desk would ask: how much can this lose, is the return worth the risk, is it actually diversified, what drives it, and how would it have done in past crises.

The project is also an exercise in building that the way a production service would be built, with clear service boundaries, failure handling, measurements, and tests that check properties rather than examples.

## Goals

- Turn an upload into a full analysis without blocking the request, and show progress live.
- Every number is reproducible: the same book on the same day gives byte-identical results.
- Adding a new analysis is one module plus one registry line, with no change to the pipeline.
- No upload is ever lost or analyzed twice into conflicting results, even when workers crash.
- Performance claims are measured, and regressions fail CI.

## Non-goals

- Trading advice or order execution. Quantly is diagnostic.
- Intraday data. Everything is daily closes.
- Always-on hosting. The AWS stack is stood up for demos and torn down after (see the README for cost).
- Transactions and tax lots. A portfolio is a snapshot of current positions.

## Architecture

```
browser ── HTTPS + JWT ──> ALB ──> api (FastAPI, Fargate)
                                     │  writes portfolio, job and outbox row in one transaction
                                     │  streams status over SSE from redis pub/sub
                                     v
                         postgres <── beat (celery beat): outbox relay, stuck-job sweeper
                                     │
                                     v
                          redis (broker, caches, pub/sub, locks, rate limits)
                                     │
                                     v
                         worker (Celery prefork, Fargate Spot, C++ engine)
                                     │  fetches missing prices (Yahoo), factors (Ken French)
                                     v
                         postgres (prices, factor returns, results)
```

The api is small, stateless and latency bound. The worker is CPU bound and bursty. They are separate services so they scale on different signals: the api on request count and CPU, the worker on queue backlog per worker.

## Request lifecycle

1. The user signs in with email and password or Google. The api issues its own short-lived access JWT and a rotating refresh token, so nothing downstream sees a Google token.
2. Upload: the api validates the CSV, stores the raw file in S3, and in one database transaction writes the portfolio, its holdings, a job row and an outbox row. It returns `202` immediately.
3. The beat process relays unpublished outbox rows to the Celery queue every two seconds (`SELECT ... FOR UPDATE SKIP LOCKED`, so several relays never double-send the same row).
4. A worker takes a per-portfolio lock, builds the analysis context, runs every analyzer, writes the results guarded by a run token, and publishes each status change to a Redis channel.
5. The browser holds a Server-Sent Events stream on `/portfolios/{id}/events`. The api sends the current status from the database first, then relays the pub/sub messages, and closes on a terminal state. If the stream fails, the client falls back to polling.

## The analysis pipeline

`compute_analytics` has two halves.

**Prepare** (`worker/analysis.py::build_context`) runs once per job. It parses the CSV, values it at current prices, loads price history, and builds an `AnalysisContext`:

- `prices` and `returns`: adjusted closes and daily returns as date-indexed frames, inner-joined so every row is a day every holding traded. An earlier version aligned series by truncating them to the same length, which silently paired one ticker's Tuesday with another's Wednesday whenever a day was missing. Date alignment fixes that, and a property test checks it.
- `portfolio_returns` and `benchmark_returns` on the same dates.
- `weights`, the current value weights.
- `full_history` back to 2007, for analyses that need older crises. Metrics use a 5 year window.

**Analyze** runs a registry of analyzers in order. Each is a function `ctx -> dict` declaring the result keys it writes. One that raises writes `{"error": ...}` for its own keys only, so a bug in the factor model never costs the user their volatility number. The frontend mirrors this: each section reads its result through a helper that hides missing or failed metrics, and each section sits in its own error boundary.

The run order is an explicit list, not import order. That was learned the hard way: the first version registered analyzers on import, isort alphabetized the imports, and the insights analyzer started running before the metrics it reads. A golden snapshot test caught it.

Results are cached in Redis by a hash of the holdings and the as-of date, so identical books on the same day share one computation. That only works if output is independent of CSV row order, which a property test checks. It caught one real violation: the frontier optimizer converges to a tolerance, so its weights differed in the eighth decimal with column order. The optimizer now runs over sorted tickers.

## Analyses, and how each works

**Core metrics.** Annualized volatility and return, Sharpe and Sortino, max drawdown and its duration, beta to SPY, the correlation matrix, and 21 day Monte Carlo VaR. These are checked against `empyrical` to about 1e-9. The deliberate differences (annual vs per-period risk-free rate, 0 instead of NaN on a flat series) are tested as relationships.

**VaR suite and backtest.** VaR and expected shortfall at 1 and 21 days, 95% and 99%, four ways: historical, parametric normal, Cornish-Fisher (adjusts the normal quantile for skew and fat tails), and Monte Carlo. The backtest rolls a 250 day window over the last two years, forecasts 1 day 95% VaR each day, and counts breaches. The Kupiec test asks whether there were too many or too few breaches; the Christoffersen test asks whether they clustered, which a good model should not allow.

**Efficient frontier.** Mean-variance optimization over the user's own holdings, long-only with a 40% cap per name. Two estimation choices matter more than the optimizer:

- Covariance uses Ledoit-Wolf shrinkage toward a scaled identity. With five years of data and a dozen assets the sample covariance is noisy, and an optimizer will happily exploit the noise.
- Expected returns are shrunk James-Stein style toward CAPM-implied returns (each asset's beta times the market's mean return), the equilibrium idea behind Black-Litterman. Raw historical means are the largest source of error in mean-variance optimization; without shrinkage, "max Sharpe" just buys whatever got lucky. The first version shrank toward the cross-sectional mean instead. On a real 13-holding portfolio the means were so noisy that every asset shrank to the same number, the frontier collapsed to a flat line, and max Sharpe equalled min variance. Shrinking toward the CAPM prior keeps the honest amount of shrinkage but still ranks assets by market exposure.

The output is the frontier, the user's position relative to it, and minimum-variance, maximum-Sharpe and risk-parity alternatives. All of it is in-sample, and the UI says so.

**Stress tests.** Six SPY-defined peak-to-trough windows from 2007 to 2022. A holding with price history covering the window is replayed on its own prices. One that did not trade then (a later IPO) is estimated as beta times SPY's move, and the result reports what share of the book was estimated. The question answered is what today's portfolio would have done, not what any real portfolio did.

**Factor model.** A regression of portfolio excess returns on the Fama-French five factors plus momentum, from Ken French's data library (refreshed weekly, keyed on the last fetch attempt because the data lags a month or two). Standard errors are Newey-West, since daily returns are autocorrelated and heteroskedastic and plain OLS standard errors would overstate significance. A tilt is only called real with |t| of at least 2.

**Risk contribution.** Euler decomposition: each holding's contribution `w_i (Σw)_i / σ_p` sums exactly to portfolio volatility. The headline is the gap between share of capital and share of risk.

## Reliability

The queue gives at-least-once delivery, so the design goal is that duplicates and crashes are harmless.

- **Transactional outbox.** Committing the upload and then enqueuing can lose the job if the process dies or the broker is down between the two. The upload writes an outbox row in the same transaction; a relay publishes it. Task ids are a `uuid5` of the job id, so a resend is recognizably the same task.
- **Per-portfolio lock.** `SET NX PX` with a random token, renewed by a heartbeat thread, released by a compare-and-delete Lua script so a slow holder can never delete a newer holder's lock. A duplicate delivery while the lock is held is a no-op.
- **Run token.** A lock without fencing can still be wrong if a worker pauses past its TTL and wakes up thinking it owns the job. Result writes are `UPDATE ... WHERE run_token = :mine`, so a stale run writes nothing.
- **Retry taxonomy.** Network errors, timeouts, Redis connection errors, database operational errors and Yahoo rate limits retry with exponential backoff and jitter, up to four attempts. Bad input fails immediately. Unknown exceptions are treated as permanent so a bug is not retried blindly. Exhausted jobs go to a dead-letter list with a script to inspect and requeue.
- **Sweeper.** A crashed worker's lock outlives it by up to 30 seconds, and Redis only redelivers an unacknowledged task after the visibility timeout (300 s, set above the longest backoff). A sweeper re-announces portfolios stuck past a threshold, which covers both.
- **Rate limiting.** A sliding-window log in a Redis sorted set, checked and recorded in one Lua script so it is atomic across api replicas and uses Redis time. Uploads are limited per user and fail closed if Redis is down; logins are limited per IP and fail open, so a Redis outage does not lock everyone out.
- **Chaos test.** `scripts/chaos.py` uploads a batch of portfolios, kills and restarts workers at random, and asserts every portfolio ends in a terminal state with exactly one set of results. It runs on a nightly workflow.

## Performance

The C++ engine (pybind11) holds the kernels where compiled code can win, with NumPy fallbacks used whenever the wheel is not installed.

- **Drawdown** is a path-dependent scan that NumPy cannot vectorize. C++ is about 43x faster.
- **Monte Carlo VaR** splits paths into fixed blocks of 1024, each with its own Philox counter-based random stream keyed by (seed, block). Any thread can compute any block in any order, so the result is bit-identical for 1 or 22 threads. On one thread it ties NumPy, because NumPy's batched normal draws are as fast per variate; the win is parallelism (5.7x on 22 threads). A Sobol quasi-Monte Carlo variant reaches the same error with roughly 10x fewer paths, but only after rotating the daily shocks onto a Helmert basis so the best-distributed Sobol dimensions carry the overall level of the path.
- **Correlation** uses a tiled, packed kernel with a runtime-dispatched AVX2 micro-kernel. It is 2x to 12x faster than the old loop and still loses to multithreaded BLAS. It is kept honest in the README rather than tuned until the table looks good.

In the worker the engine runs single-threaded (`engine_threads = 1`): Celery already runs one process per core, and every process spawning a thread per core would oversubscribe the machine. Multithreading helps a single large job, not a busy queue.

CI runs the benchmarks three times and fails if any single-thread C++/NumPy ratio drops more than 15% below a committed baseline. Ratios cancel most of the difference between runners; absolute times would not.

## Observability

Everything is behind `QUANTLY_OTEL_ENABLED` and a no-op otherwise.

- **Traces.** OpenTelemetry spans for the request, the database, Redis, the Celery publish and task, and every analyzer. Trace context rides in the Celery task headers, so one trace covers the request through to the last analyzer.
- **Metrics.** Prometheus histograms for request latency and job and analyzer duration, a queue depth gauge read at scrape time, and counters for cache hits, retries, failures and dead-lettered jobs. Histograms rather than summaries, because bucket counts can be summed across replicas and summary quantiles cannot.
- **SLOs.** Availability, upload accept latency and analysis time, with multiwindow, multi-burn-rate alerts ([docs/slo.md](slo.md)). The latency thresholds are histogram bucket bounds, so the SLI is an exact ratio rather than an interpolated quantile.

## Testing

- Unit and API tests, plus a golden snapshot that pins the full analytics output on a fixed book and fixed prices. It runs on the NumPy path so it holds with or without the engine.
- Hypothesis property tests: correlation bounds and symmetry, drawdown bounds, shift and scale behaviour of volatility and Sharpe, beta of a series with itself, VaR monotone in confidence, row-order invariance of the whole pipeline, and date alignment under dropped days.
- Fuzzing: Atheris on the CSV parser (only a validation error may escape; it found two inputs that would have been 500s) and libFuzzer on the C++ kernels. ASan and UBSan builds of the engine tests in CI.
- Catch2 tests for the engine, including thread-count invariance and QMC beating MC at equal path counts.
- Playwright end-to-end tests against the compose stack, with seeded prices so CI never touches Yahoo.
- The test suite blocks network access, so a test that would silently download data fails instead.

## What running it under load found

Unit and property tests passed before any of this. Running the real stack under k6 and a chaos script found five problems none of them could see, because each needs real concurrency, a real connection pool, or a real container:

1. **First analysis of a new ticker ran without its history.** The worker session has autoflush off, so bars fetched earlier in a job were not visible to the read that followed. The unit tests used sessions with autoflush on. Fixed by flushing after the write, with a regression test on an autoflush-off session.
2. **Two jobs fetching the same new ticker raced.** Both inserted the same price rows, the second hit a duplicate key, and the error was (correctly) classified as permanent, so the job failed. Shared-table writes are now `INSERT ... ON CONFLICT DO NOTHING`, for prices, factor returns and the backfill bookkeeping.
3. **The api ran out of database connections.** SQLAlchemy's default pool (5 + 10) is smaller than FastAPI's 40-thread pool for sync endpoints, so under a burst requests waited 30 s for a connection and then failed with a 500. The pool is now sized to the thread pool, times out after 5 s, and an exhausted pool returns 503 with `Retry-After`: overload is load shedding, not an error page.
4. **Housekeeping waited behind the work.** The outbox relay and sweeper ran on the analysis queue, so a backlog of jobs delayed the relay that publishes new uploads, and missed ticks piled up. They now have their own queue (workers consume both) and their ticks expire.
5. **The worker crashed on start in the default compose stack.** The Prometheus multiprocess directory was a root-owned tmpfs and the worker runs as a non-root user. The load-test override masked it; the chaos script, which recreates workers from the base file, exposed it.

Looking at the rendered page, not just the tests, found two more: the collapsed efficient frontier described above, and a factor section that crashed (instead of hiding) when no factor data had been downloaded yet. The download itself had failed because batching the race fix into one multi-row insert went past Postgres's 65,535 bind parameter limit; inserts are now batched.

Measured capacity is in [docs/capacity.md](capacity.md). In short: one api process on one CPU serves about 100 requests/s (20 uploads/s plus reads) at upload p99 around 50 ms, and a worker on 2 CPUs analyzes about 2 portfolios/s once prices are stored, scaling to about 6/s with 4 workers.

## Alternatives considered

- **Polling vs SSE vs WebSockets for job status.** Polling was the first version and wastes requests while a job runs. WebSockets are bidirectional, which this does not need, and are awkward behind some proxies. SSE is one long HTTP response, works through the ALB with a heartbeat, and the client falls back to polling. Browser `EventSource` cannot send an Authorization header, so the client reads the stream with `fetch` instead of putting the JWT in the URL.
- **Enqueue after commit vs outbox.** Enqueue after commit is simpler and almost always works. "Almost always" means a stuck pending portfolio every time the broker blips during an upload. The outbox costs one table and up to two seconds of latency.
- **Distributed lock vs idempotent writes only.** Idempotent writes alone would let two workers compute the same job at once, wasting a worker on every duplicate delivery. The lock prevents the wasted work; the run token keeps the result correct when the lock is not enough.
- **More C++.** Moving the whole pipeline to C++ would speed up code that is already fast enough and make every analysis harder to change. The engine holds the three kernels where measurement showed it matters.
- **Optimizer library (cvxpy) vs scipy.** cvxpy is the better tool for larger problems, but it is a heavy dependency for a 15-asset long-only problem. scipy's SLSQP with warm starts and a convex risk-parity formulation is enough and easy to test.

## Scaling to 100x

Today's bottlenecks, in order:

1. **Market data.** Every new ticker costs a Yahoo fetch back to 2007. At 100x users this needs a scheduled nightly bulk refresh for the most-held tickers and a paid data source with an SLA. The prices table is already shared across users, so storage grows with distinct tickers, not users.
2. **Workers.** They are stateless and scale out on backlog per worker (see [docs/capacity.md](capacity.md)). Spot capacity keeps that cheap; a Spot interruption is just another crash the lock, retries and sweeper already handle.
3. **Postgres.** Results are written once per job and read on page loads. The first steps are a read replica for the api and partitioning `prices` by ticker. The outbox relay's `SKIP LOCKED` lets several relays run in parallel.
4. **Redis.** It does five jobs (broker, caches, pub/sub, locks, rate limits). At scale the broker should move to its own instance or to SQS so a cache eviction storm cannot delay jobs.
5. **SSE connections.** Each open stream holds an api connection and a Redis pub/sub connection for up to 10 minutes. At 100x that argues for one shared pub/sub subscription per api process, fanned out in memory, instead of one per stream.
