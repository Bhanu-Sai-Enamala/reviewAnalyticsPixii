from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./backend/review_analytics.db"
    backend_cors_origins: str = "http://localhost:5173"
    anthropic_api_key: Optional[str] = None
    claude_model: str = "claude-3-5-sonnet-latest"
    scraper_provider: str = "playwright"
    bright_data_api_key: Optional[str] = None
    bright_data_zone: Optional[str] = None
    bright_data_host: Optional[str] = None
    bright_data_username: Optional[str] = None
    bright_data_password: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
