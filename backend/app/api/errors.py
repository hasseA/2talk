"""Centralized mapping from API and service exceptions to public errors."""

from collections.abc import Mapping

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.services import (
    ConversationAlreadyEndedError,
    ConversationEndedError,
    ConversationFullError,
    ConversationNotActiveError,
    ConversationNotFoundError,
    ConversationStateError,
    DuplicateMessageError,
    InvalidCursorError,
    InvitationAlreadyUsedError,
    InvitationExpiredError,
    InvitationNotFoundError,
    InvitationRevokedError,
    MessageNotFoundError,
    MessageNotRetryableError,
    MessageStateError,
    ParticipantNotFoundError,
    ServiceError,
    SummaryNotFoundError,
)

ErrorMapping = tuple[int, str, str]

SERVICE_ERRORS: Mapping[type[ServiceError], ErrorMapping] = {
    ConversationAlreadyEndedError: (
        409,
        "CONVERSATION_ALREADY_ENDED",
        "Conversation has already ended.",
    ),
    ConversationNotFoundError: (
        404,
        "CONVERSATION_NOT_FOUND",
        "Conversation not found.",
    ),
    ConversationFullError: (409, "CONVERSATION_FULL", "Conversation is full."),
    ConversationEndedError: (409, "CONVERSATION_ENDED", "Conversation has ended."),
    ConversationStateError: (409, "CONVERSATION_STATE", "Invalid conversation state."),
    ConversationNotActiveError: (
        409,
        "CONVERSATION_NOT_ACTIVE",
        "Conversation is not active.",
    ),
    InvitationNotFoundError: (
        404,
        "INVALID_INVITATION",
        "This invitation is invalid or no longer available.",
    ),
    InvitationExpiredError: (410, "INVITATION_EXPIRED", "Invitation has expired."),
    InvitationAlreadyUsedError: (
        409,
        "INVITATION_ALREADY_USED",
        "Invitation was used.",
    ),
    InvitationRevokedError: (
        404,
        "INVALID_INVITATION",
        "This invitation is invalid or no longer available.",
    ),
    ParticipantNotFoundError: (403, "FORBIDDEN", "Participant is not authorized."),
    MessageNotFoundError: (404, "MESSAGE_NOT_FOUND", "Message not found."),
    MessageNotRetryableError: (
        409,
        "MESSAGE_NOT_RETRYABLE",
        "Message is not retryable.",
    ),
    DuplicateMessageError: (409, "DUPLICATE_MESSAGE", "Message already exists."),
    MessageStateError: (409, "MESSAGE_STATE", "Invalid message state."),
    SummaryNotFoundError: (404, "SUMMARY_NOT_FOUND", "Summary not found."),
    InvalidCursorError: (400, "INVALID_CURSOR", "Pagination cursor is invalid."),
}


def register_exception_handlers(app: FastAPI) -> None:
    """Install all exception handlers once at application construction."""
    app.add_exception_handler(ServiceError, service_error_handler)
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)


async def service_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    status_code, code, message = SERVICE_ERRORS.get(
        type(exc), (500, "INTERNAL_ERROR", "An unexpected error occurred.")
    )
    return _error_response(status_code, code, message)


async def http_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, HTTPException)
    if isinstance(exc.detail, dict):
        code = str(exc.detail.get("code", "HTTP_ERROR"))
        message = str(exc.detail.get("message", "Request failed."))
    else:
        code = "HTTP_ERROR"
        message = str(exc.detail)
    return _error_response(exc.status_code, code, message, headers=exc.headers)


async def validation_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    errors = exc.errors()
    if any(
        error["loc"][-1] == "preferred_language"
        and error["type"] in {"literal_error", "enum"}
        for error in errors
    ):
        return _error_response(
            422,
            "UNSUPPORTED_LANGUAGE",
            "The requested language is not supported.",
        )
    if any(
        error["loc"][-1] == "message" and error["type"] == "string_too_long"
        for error in errors
    ):
        return _error_response(422, "MESSAGE_TOO_LONG", "Message is too long.")
    if any(
        error["loc"][-1] == "message"
        and error["type"] in {"string_too_short", "value_error"}
        for error in errors
    ):
        return _error_response(422, "EMPTY_MESSAGE", "Message must not be empty.")
    details = [
        {"field": ".".join(str(part) for part in error["loc"]), "message": error["msg"]}
        for error in errors
    ]
    return _error_response(
        422,
        "VALIDATION_ERROR",
        "The request contains invalid fields.",
        details=details,
    )


async def unexpected_error_handler(_request: Request, _exc: Exception) -> JSONResponse:
    return _error_response(500, "INTERNAL_ERROR", "An unexpected error occurred.")


def _error_response(
    status_code: int,
    code: str,
    message: str,
    *,
    details: object | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    error: dict[str, object] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "error": error},
        headers=headers,
    )
