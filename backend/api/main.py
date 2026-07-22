from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import auth, health, portfolios
from common.config import get_settings

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


@app.get("/")
def root():
    return {"message": "Quantly API"}
