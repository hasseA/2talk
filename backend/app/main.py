"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.errors import register_exception_handlers
from app.api.main import api_router


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Release database resources when the application stops."""
    yield
    from app.database.session import dispose_engine

    await dispose_engine()


def create_app() -> FastAPI:
    """Construct the FastAPI application and its versioned REST boundary."""
    application = FastAPI(title="2talk API", lifespan=lifespan)
    register_exception_handlers(application)
    application.include_router(api_router)
    return application


app = create_app()
