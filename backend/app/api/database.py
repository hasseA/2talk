"""Lazy database-session dependency for the REST boundary."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield a session without loading environment settings at import time."""
    from app.database.session import get_session

    async for session in get_session():
        yield session
