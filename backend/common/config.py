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

    # object storage. defaults point at the local minio in docker-compose.
    # in prod, unset the endpoint url and let the iam role supply credentials.
    s3_bucket: str = "quantly-portfolios"
    s3_region: str = "us-east-1"
    s3_endpoint_url: str | None = "http://localhost:9000"
    aws_access_key_id: str | None = "minioadmin"
    aws_secret_access_key: str | None = "minioadmin"

    # reject uploads larger than this many bytes
    max_upload_bytes: int = 5_000_000


@lru_cache
def get_settings() -> Settings:
    return Settings()
