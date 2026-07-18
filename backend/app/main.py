"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Release database resources when the application stops."""
    yield
    from app.database.session import dispose_engine

    await dispose_engine()


app = FastAPI(title="2talk API", lifespan=lifespan)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Report that the application process is running."""
    return {"status": "ok"}
