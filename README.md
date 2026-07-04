# Quantly

Portfolio analytics platform — upload your holdings and get real risk & performance insights, not just "what's it worth."

## Overview

Quantly turns a CSV of your stock holdings into the analytics your brokerage screen doesn't give you: how risky your portfolio actually is, whether you're being paid for that risk, and whether you're genuinely diversified. You upload a portfolio, the backend fetches historical market data and runs performance/risk calculations, and the results are returned for interactive visualization.

It's a hybrid **Python/C++** system: latency-sensitive API work in FastAPI, with the heavy number-crunching in a C++ engine exposed to Python via pybind11.

## What it does

Beyond current value and gain/loss, Quantly surfaces risk & diversification insights — each paired with a plain-English interpretation, not just a number:

- **Volatility & max drawdown** — how much your portfolio could realistically fall.
- **Sharpe / Sortino ratio** — whether your returns justify the risk you're taking.
- **Correlation matrix** — whether your holdings actually diversify you, or all move together.
- **Beta** — how your portfolio moves relative to the market.
- **Allocation & concentration** — how exposed you are to any single position.

## Tech Stack

### Frontend
- React
- TypeScript
- Tailwind CSS
- Lightweight Charts (TradingView)
- TanStack Query

### Backend
- FastAPI
- Python (pandas, NumPy)
- C++ (via pybind11)
- JWT authentication (PyJWT)
- SQL (PostgreSQL)

### Data & Infrastructure
- AWS S3 (portfolio file storage)
- AWS RDS (user, portfolio, and analytics metadata)
- AWS ECS Fargate (FastAPI API + async worker)
- Celery + Redis (async job processing)
- Docker, Terraform

## Architecture (target)

```
React frontend  ──HTTPS/JWT──▶  FastAPI API  ──enqueue──▶  Redis  ──▶  Celery worker
                                    │                                      │
                              RDS (Postgres)                     Yahoo data + C++ engine
                                    │                                      │
                                   S3 (raw CSVs)  ◀───────────────  results → RDS
```

The API stays fast and stateless; heavy analysis runs asynchronously in a separate worker so uploads never block on compute. Market data is fetched lazily per ticker and cached/stored once, shared across all portfolios.

## Getting Started

### Prerequisites
- Python 3.13+

### Run the backend
```bash
cd backend/app
python -m venv .venv

# Windows (PowerShell):   .venv\Scripts\Activate.ps1
# Windows (Git Bash):     source .venv/Scripts/activate
# macOS / Linux:          source .venv/bin/activate

pip install -r requirements.txt
uvicorn main:app --reload
```

The API runs at `http://127.0.0.1:8000` with interactive docs at `/docs`.

### Try it
Upload one of the sample files in [`example_csv/`](./example_csv) to `POST /upload`, then hit `GET /portfolio` and `GET /summary` to see parsed positions, current values, and gain/loss.

## Status

Early, active development. The valuation pipeline (CSV upload → live prices → gain/loss) works today; auth, the C++ analytics engine, async processing, and cloud infrastructure are in progress.

## Motivation

Quantly is both a personal and technical project. The scale and richness of financial data allow for advanced analytics and meaningful performance insights that apply directly to my own portfolio — building a tool that helps with real investing decisions makes it personally motivating and technically challenging. It's also a vehicle for going deep on production system design: async processing, infrastructure-as-code, benchmarked C++ performance work, and secure modern auth.
