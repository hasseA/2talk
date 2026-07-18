"""Shared API response envelopes."""

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel

DataT = TypeVar("DataT")


class SuccessResponse(BaseModel, Generic[DataT]):  # noqa: UP046
    """Documented success envelope."""

    success: Literal[True] = True
    data: DataT


class ErrorBody(BaseModel):
    """Stable public error representation."""

    code: str
    message: str
    details: object | None = None


class ErrorResponse(BaseModel):
    """Documented error envelope."""

    success: Literal[False] = False
    error: ErrorBody
