"""Small shared helpers for single-entity repositories."""

from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(
    Generic[ModelT]  # noqa: UP046  # Keep Python 3.11 tooling support.
):
    """Provide transparent persistence helpers without owning transactions."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, entity_id: UUID) -> ModelT | None:
        return await self.session.get(self.model, entity_id)

    async def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def delete(self, entity: ModelT) -> None:
        await self.session.delete(entity)
        await self.session.flush()

    async def flush(self) -> None:
        await self.session.flush()

    async def refresh(self, entity: ModelT) -> ModelT:
        await self.session.refresh(entity)
        return entity
