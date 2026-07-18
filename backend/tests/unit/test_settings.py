"""Typed settings tests."""

import pytest
from pydantic import SecretStr

from app.config.settings import Settings


def test_settings_load_required_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost/twotalk_test",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    monkeypatch.setenv("SESSION_TOKEN_SECRET", "session-test-secret")
    monkeypatch.setenv("INVITATION_TOKEN_SECRET", "invitation-test-secret")

    settings = Settings()  # type: ignore[call-arg]

    assert settings.app_env == "test"
    assert settings.database_url.endswith("/twotalk_test")
    assert isinstance(settings.openai_api_key, SecretStr)
    assert "not-a-real-key" not in repr(settings.openai_api_key)
