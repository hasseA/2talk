"""Documented participant preference schemas."""

from pydantic import BaseModel

from app.api.schemas.common import SuccessResponse
from app.api.schemas.conversation import LanguageCode, ParticipantProfileResponse


class UpdateLanguageRequest(BaseModel):
    preferred_language: LanguageCode


class UpdateLanguageData(BaseModel):
    participant: ParticipantProfileResponse


class UpdateLanguageResponse(SuccessResponse[UpdateLanguageData]):
    pass
