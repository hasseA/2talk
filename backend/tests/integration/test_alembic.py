"""Alembic lifecycle test against a clean PostgreSQL database."""

import asyncio
from pathlib import Path

from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

import app.models  # noqa: F401
from alembic import command
from app.database.base import Base

EXPECTED_TABLES = {
    "ai_mediation_jobs",
    "ai_processing_attempts",
    "conversation_summaries",
    "conversations",
    "invitations",
    "message_deliveries",
    "messages",
    "participant_sessions",
    "participants",
    "private_guidance",
    "safety_events",
}


async def get_table_names(database_url: str) -> set[str]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            names = await connection.run_sync(
                lambda sync_connection: inspect(sync_connection).get_table_names()
            )
        return set(names)
    finally:
        await engine.dispose()


async def reset_database(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    finally:
        await engine.dispose()


def alembic_config(database_url: str) -> Config:
    backend_dir = Path(__file__).resolve().parents[2]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_alembic_upgrade_downgrade_and_upgrade_again(test_database_url: str) -> None:
    config = alembic_config(test_database_url)
    asyncio.run(reset_database(test_database_url))

    command.upgrade(config, "head")
    assert EXPECTED_TABLES <= asyncio.run(get_table_names(test_database_url))

    command.downgrade(config, "20260718_0001")
    downgraded_tables = asyncio.run(get_table_names(test_database_url))
    assert "ai_mediation_jobs" not in downgraded_tables
    assert "messages" in downgraded_tables

    command.upgrade(config, "head")
    assert EXPECTED_TABLES <= asyncio.run(get_table_names(test_database_url))
