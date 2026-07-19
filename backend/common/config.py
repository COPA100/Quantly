from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration, loaded from environment variables (QUANTLY_*) or a local .env file."""

    model_config = SettingsConfigDict(env_prefix="QUANTLY_", env_file=".env", extra="ignore")

    app_name: str = "Quantly"
    environment: str = "dev"
    cors_origins: list[str] = ["http://localhost:5173"]
    # default matches the docker-compose postgres service
    database_url: str = "postgresql+psycopg://quantly:quantly@localhost:5432/quantly"


@lru_cache
def get_settings() -> Settings:
    return Settings()
