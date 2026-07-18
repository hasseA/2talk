"""Versioned REST router assembly."""

from datetime import UTC, datetime

from fastapi import APIRouter

from app.api.routers import (
    conversations,
    invitations,
    messages,
    participants,
    summaries,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(conversations.router)
api_router.include_router(invitations.router)
api_router.include_router(participants.router)
api_router.include_router(messages.router)
api_router.include_router(summaries.router)


@api_router.get("/health", tags=["system"])
async def api_health() -> dict[str, object]:
    return {
        "success": True,
        "data": {"status": "ok", "timestamp": datetime.now(UTC)},
    }


@api_router.get("/languages", tags=["system"])
async def supported_languages() -> dict[str, object]:
    return {
        "success": True,
        "data": {
            "languages": [
                {"code": "en", "name": "English"},
                {"code": "sv", "name": "Swedish"},
                {"code": "fa", "name": "Persian"},
            ]
        },
    }
