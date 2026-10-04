# SLOs and alerting

Metrics come from `backend/common/telemetry.py`; rules live in `ops/prometheus/alerts.yml`.

## SLIs and SLOs

All SLOs use a rolling 30 day window.

| SLO | SLI (good events / valid events) | Target |
|---|---|---|
| Availability | API requests that did not return 5xx / all API requests (`/metrics` excluded) | 99.9% |
| Upload accept latency | `POST /portfolios` answered in under 300 ms / all `POST /portfolios` | 99.5% |
| Analysis time | `analyze_portfolio` tasks that finished in under 60 s / all tasks | 95% |

Notes on the definitions:

- Latency is measured to the response headers by the ASGI middleware, so it is time to first byte. The 300 ms and 60 s thresholds are histogram bucket bounds, which makes the SLI an exact bucket ratio instead of an interpolated quantile.
- Upload accept latency covers only the synchronous part (validate, write to S3, enqueue). It is the part the user waits on. The analysis itself is the third SLO.
- Analysis time is task wall time on the worker, not enqueue to finish, so queue wait is not included. Queue wait is watched through the `QueueBacklog` alert and the queue depth panel.
- Failed jobs are tracked separately by `JobFailureRatio` (more than 10% over 15 minutes), not folded into the analysis time SLI.

## Error budget math

The budget is `1 - target`, measured in events over the window.

| SLO | Budget | In time terms over 30 days |
|---|---|---|
| Availability 99.9% | 0.1% | about 43 minutes of full outage |
| Upload latency 99.5% | 0.5% | 0.5% of uploads may be slow; at 1,000 uploads a day that is 150 |
| Analysis time 95% | 5% | 1 job in 20 may exceed 60 s |

Burn rate is the observed error ratio divided by the budget. A burn rate of 1 spends the budget exactly over the window; 14.4 spends it in 30 / 14.4, roughly 2 days. At 14.4x for one hour, 2% of the 30 day budget is gone (`14.4 * 1h / 720h`).

## Burn-rate alerts

Each SLO has four alerts (the multiwindow, multi-burn-rate pattern from the Google SRE Workbook). An alert fires only when both its long and short window exceed the threshold:

| Severity | Burn rate | Long window | Short window | Budget spent when it fires |
|---|---|---|---|---|
| page | 14.4x | 1 h | 5 m | 2% |
| page | 6x | 6 h | 30 m | 5% |
| ticket | 3x | 1 d | 2 h | 10% |
| ticket | 1x | 3 d | 6 h | 10% |

The long window makes the alert significant (it needs real budget loss, not a blip). The short window makes it reset quickly once the problem is fixed, so the alert does not keep firing for an hour after recovery. The threshold is `burn rate * budget`, for example `14.4 * 0.001 = 0.0144` for availability.

Recording rules (`slo:<name>:error_ratio_rate<window>`) compute each error ratio once per window, and the alerts compare those series. With no traffic the ratio is NaN and nothing fires, which is acceptable for a service that can sit idle; the `ScrapeTargetDown` alert covers a dead target.

Other alerts: `QueueBacklog` (more than 50 queued tasks for 10 minutes), `JobFailureRatio`, `DeadLetterGrowing`, `ScrapeTargetDown`.

## Validation

Run `promtool check rules ops/prometheus/alerts.yml` when promtool is installed. promtool was not available when this was written, so the file was only checked as YAML. Prometheus loads the same file in the `obs` compose profile and shows rule errors at `http://localhost:9090/rules`.
