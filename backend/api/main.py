from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import TimeoutError as PoolTimeoutError

from api.routers import auth, health, portfolios
from common.config import get_settings
from common.telemetry import instrument_api

settings = get_settings()

app = FastAPI(title=settings.app_name)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(portfolios.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(PoolTimeoutError)
async def shed_load(request: Request, exc: PoolTimeoutError) -> JSONResponse:
    # every db connection is busy: the api is overloaded, not broken. a 503 with
    # retry-after tells clients and the load balancer to back off, where a 500
    # would read as a bug and count against the error budget as one.
    return JSONResponse(
        status_code=503,
        content={"detail": "server busy, retry shortly"},
        headers={"Retry-After": "1"},
    )


instrument_api(app)


@app.get("/")
def root():
    return {"message": "Quantly API"}
