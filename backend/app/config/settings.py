"""Typed environment-backed application settings."""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration loaded from environment variables or a local .env file."""

    app_env: str
    database_url: str
    openai_api_key: SecretStr
    openai_model: str = "gpt-5-mini"
    openai_timeout_seconds: float = Field(default=30.0, gt=0)
    openai_max_output_tokens: int = Field(default=2000, gt=0)
    session_token_secret: SecretStr
    invitation_token_secret: SecretStr

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide immutable settings instance."""
    return Settings()  # type: ignore[call-arg]
