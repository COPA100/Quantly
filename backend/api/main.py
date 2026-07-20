import os
import tempfile

from fastapi import FastAPI, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from api.routers import health, portfolios
from common.analytics.basic import (
    calculate_portfolio_gainloss,
    calculate_portfolio_total,
    calculate_position_gains,
)
from common.config import get_settings
from common.csv_reader import parse_portfolio
from common.market_data import fetch_current_prices

settings = get_settings()

app = FastAPI(title=settings.app_name)

app.include_router(health.router)
app.include_router(portfolios.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

portfolio = []


@app.get("/")
def root():
    return {"message": "Quantly API"}


@app.post("/upload")
async def upload(file: UploadFile):
    global portfolio

    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    portfolio = parse_portfolio(tmp_path)
    portfolio = fetch_current_prices(portfolio)
    portfolio = calculate_position_gains(portfolio)

    os.remove(tmp_path)
    return {"message": "Uploaded", "positions": len(portfolio)}


@app.get("/portfolio")
def get_portfolio():
    if not portfolio:
        return {"error": "No portfolio uploaded"}
    return portfolio


@app.get("/summary")
def summary():
    if not portfolio:
        return {"error": "No portfolio uploaded"}
    return {
        "total": calculate_portfolio_total(portfolio),
        **calculate_portfolio_gainloss(portfolio),
    }
