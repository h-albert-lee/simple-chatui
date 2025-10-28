from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Backend
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    # URL exposed to the Streamlit frontend for chat completions
    BACKEND_API_URL: AnyHttpUrl = "http://localhost:8000/api/v1/chat/completions"

    # Upstream OpenAI-compatible API
    UPSTREAM_API_BASE: AnyHttpUrl
    UPSTREAM_API_KEY: str = ""
    DEFAULT_MODEL: str = "gpt-3.5-turbo"

    # Persistence
    DATABASE_URL: str = "sqlite:///chat_history.db"

    # Authentication
    AUTH_TOKEN_TTL_HOURS: int = 24 * 7

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:8501"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def split_cors_origins(cls, value: object) -> List[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value  # type: ignore[return-value]

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if not value.startswith("sqlite:///"):
            raise ValueError("Only sqlite:/// URLs are supported for DATABASE_URL")
        return value

    @property
    def database_path(self) -> Path:
        return Path(self.DATABASE_URL.replace("sqlite:///", "")).expanduser().resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""

    return Settings()


settings = get_settings()
