from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Polymarket
    polymarket_clob_url: str = "https://clob.polymarket.com"
    gamma_api_url: str = "https://gamma-api.polymarket.com"
    polymarket_api_key: str = ""
    polymarket_api_secret: str = ""
    polymarket_passphrase: str = ""

    # Storage
    database_url: str = "postgresql+asyncpg://polyprism:polyprism@localhost:5432/polyprism"
    redis_url: str = "redis://localhost:6379/0"

    # App
    log_level: str = "INFO"
    env: str = "development"

    # Ingestion tuning
    snapshot_interval_seconds: int = 60
    max_markets_to_track: int = 200


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
