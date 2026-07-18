"""FastAPI TestClient wired to the PostgreSQL integration database."""

from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.api.database import get_db_session
from app.config import Settings, get_settings
from app.main import create_app


@pytest.fixture
def api_settings(test_database_url: str) -> Settings:
    return Settings(
        app_env="test",
        database_url=test_database_url,
        openai_api_key="not-used",
        session_token_secret="session-api-test-secret",
        invitation_token_secret="invitation-api-test-secret",
    )


@pytest.fixture
def api_app(db_engine: AsyncEngine, api_settings: Settings) -> FastAPI:
    application = create_app()
    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    application.dependency_overrides[get_db_session] = override_session
    application.dependency_overrides[get_settings] = lambda: api_settings
    return application


@pytest.fixture
def api_client(api_app: FastAPI) -> Iterator[TestClient]:
    client = TestClient(api_app, raise_server_exceptions=False)
    yield client
    client.close()
