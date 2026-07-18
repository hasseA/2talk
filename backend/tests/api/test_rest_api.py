"""PostgreSQL integration coverage for the documented REST contract."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import hash_token
from app.config import Settings
from app.models import GuidanceAudience, GuidanceType
from app.repositories import InvitationRepository, ParticipantSessionRepository
from app.services import GuidanceInput, MessageLifecycleService, SummaryService


def _authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_conversation(client: TestClient, *, name: str = "Creator") -> dict:
    response = client.post(
        "/api/v1/conversations",
        json={
            "title": "API conversation",
            "display_name": name,
            "preferred_language": "sv",
            "description": "Contract reconciliation",
        },
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert set(data["conversation"]) == {
        "id",
        "title",
        "description",
        "status",
        "created_at",
    }
    assert set(data["invitation"]) == {"token", "url"}
    return data


def _join_conversation(client: TestClient, created: dict) -> dict:
    token = created["invitation"]["token"]
    response = client.post(
        f"/api/v1/invitations/{token}/join",
        json={"display_name": "Invitee", "preferred_language": "en"},
    )
    assert response.status_code == 201
    return response.json()["data"]


def test_conversation_invitation_participant_and_end_contract(
    api_client: TestClient,
) -> None:
    created = _create_conversation(api_client)
    token = created["invitation"]["token"]

    validation = api_client.get(f"/api/v1/invitations/{token}")
    assert validation.status_code == 200
    assert validation.json()["data"] == {
        "valid": True,
        "conversation": {"title": "API conversation", "status": "waiting"},
    }

    joined = _join_conversation(api_client, created)
    conversation_id = created["conversation"]["id"]
    assert set(joined["conversation"]) == {"id", "title", "status"}

    detail = api_client.get(
        f"/api/v1/conversations/{conversation_id}",
        headers=_authorization(created["session_token"]),
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["other_participant"]["display_name"] == "Invitee"

    language = api_client.patch(
        f"/api/v1/conversations/{conversation_id}/participants/me",
        headers=_authorization(created["session_token"]),
        json={"preferred_language": "fa"},
    )
    assert language.status_code == 200
    assert set(language.json()["data"]["participant"]) == {
        "id",
        "display_name",
        "preferred_language",
    }
    assert language.json()["data"]["participant"]["preferred_language"] == "fa"

    ended = api_client.post(
        f"/api/v1/conversations/{conversation_id}/end",
        headers=_authorization(joined["session_token"]),
        json={"generate_summary": True},
    )
    assert ended.status_code == 200
    assert ended.json()["data"]["conversation"]["status"] == "ended"
    assert ended.json()["data"]["summary_status"] == "processing"

    already_ended = api_client.post(
        f"/api/v1/conversations/{conversation_id}/end",
        headers=_authorization(created["session_token"]),
        json={"generate_summary": False},
    )
    assert already_ended.status_code == 409
    assert already_ended.json()["error"]["code"] == "CONVERSATION_ALREADY_ENDED"


@pytest.mark.asyncio
async def test_message_history_pagination_and_guidance_are_participant_safe(
    api_client: TestClient, db_session: AsyncSession
) -> None:
    created = _create_conversation(api_client)
    joined = _join_conversation(api_client, created)
    conversation_id = UUID(created["conversation"]["id"])
    creator_id = UUID(created["participant"]["id"])
    invitee_id = UUID(joined["participant"]["id"])

    first_response = api_client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=_authorization(created["session_token"]),
        json={"client_message_id": "client-api-1", "message": "creator raw"},
    )
    assert first_response.status_code == 202
    first_id = UUID(first_response.json()["data"]["message"]["id"])
    await MessageLifecycleService(db_session).mark_delivered(
        message_id=first_id,
        recipient_id=invitee_id,
        mediated_message="creator mediated",
        delivered_language="en",
        guidance=(
            GuidanceInput(
                participant_id=creator_id,
                audience=GuidanceAudience.SENDER,
                guidance_type=GuidanceType.COMMUNICATION_SUPPORT,
                guidance_text="creator-only guidance",
            ),
            GuidanceInput(
                participant_id=invitee_id,
                audience=GuidanceAudience.RECIPIENT,
                guidance_type=GuidanceType.DE_ESCALATION,
                guidance_text="invitee-only guidance",
            ),
        ),
    )

    second_response = api_client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=_authorization(joined["session_token"]),
        json={"client_message_id": "client-api-2", "message": "invitee raw"},
    )
    second_id = UUID(second_response.json()["data"]["message"]["id"])
    await MessageLifecycleService(db_session).mark_delivered(
        message_id=second_id,
        recipient_id=creator_id,
        mediated_message="invitee mediated",
        delivered_language="sv",
    )

    first_page = api_client.get(
        f"/api/v1/conversations/{conversation_id}/messages",
        params={"limit": 1},
        headers=_authorization(created["session_token"]),
    )
    assert first_page.status_code == 200
    first_page_data = first_page.json()["data"]
    assert first_page_data["has_more"] is True
    assert first_page_data["next_cursor"] == str(first_id)
    assert first_page_data["messages"][0]["direction"] == "outgoing"
    assert first_page_data["messages"][0]["original_message"] == "creator raw"

    second_page = api_client.get(
        f"/api/v1/conversations/{conversation_id}/messages",
        params={"after": str(first_id), "limit": 50},
        headers=_authorization(created["session_token"]),
    )
    incoming = second_page.json()["data"]["messages"][0]
    assert incoming["direction"] == "incoming"
    assert incoming["mediated_message"] == "invitee mediated"
    assert "original_message" not in incoming

    recipient_history = api_client.get(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=_authorization(joined["session_token"]),
    )
    recipient_first = recipient_history.json()["data"]["messages"][0]
    assert recipient_first["direction"] == "incoming"
    assert recipient_first["mediated_message"] == "creator mediated"
    assert "original_message" not in recipient_first

    creator_guidance = api_client.get(
        f"/api/v1/conversations/{conversation_id}/guidance",
        params={"limit": 50},
        headers=_authorization(created["session_token"]),
    )
    invitee_guidance = api_client.get(
        f"/api/v1/conversations/{conversation_id}/guidance",
        headers=_authorization(joined["session_token"]),
    )
    assert [item["text"] for item in creator_guidance.json()["data"]["guidance"]] == [
        "creator-only guidance"
    ]
    assert [item["text"] for item in invitee_guidance.json()["data"]["guidance"]] == [
        "invitee-only guidance"
    ]
    assert "seen_at" not in creator_guidance.json()["data"]["guidance"][0]

    invalid_cursor = api_client.get(
        f"/api/v1/conversations/{conversation_id}/messages",
        params={"after": "00000000-0000-0000-0000-000000000001"},
        headers=_authorization(created["session_token"]),
    )
    assert invalid_cursor.status_code == 400
    assert invalid_cursor.json()["error"]["code"] == "INVALID_CURSOR"


@pytest.mark.asyncio
async def test_message_status_retry_and_sender_ownership(
    api_client: TestClient, db_session: AsyncSession
) -> None:
    created = _create_conversation(api_client)
    joined = _join_conversation(api_client, created)
    conversation_id = created["conversation"]["id"]
    response = api_client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=_authorization(created["session_token"]),
        json={"client_message_id": "retry-id", "message": "retry raw"},
    )
    message_id = UUID(response.json()["data"]["message"]["id"])
    await MessageLifecycleService(db_session).mark_failed(
        message_id, failure_code="AI_PROCESSING_FAILED"
    )

    status_response = api_client.get(
        f"/api/v1/conversations/{conversation_id}/messages/{message_id}",
        headers=_authorization(created["session_token"]),
    )
    assert status_response.status_code == 200
    assert status_response.json()["data"]["message"] == {
        "id": str(message_id),
        "status": "failed",
        "failure_code": "AI_PROCESSING_FAILED",
        "retry_allowed": True,
    }

    forbidden = api_client.get(
        f"/api/v1/conversations/{conversation_id}/messages/{message_id}",
        headers=_authorization(joined["session_token"]),
    )
    assert forbidden.status_code == 403

    retried = api_client.post(
        f"/api/v1/conversations/{conversation_id}/messages/{message_id}/retry",
        headers=_authorization(created["session_token"]),
    )
    assert retried.status_code == 202
    assert retried.json()["data"]["message"]["status"] == "processing"

    not_retryable = api_client.post(
        f"/api/v1/conversations/{conversation_id}/messages/{message_id}/retry",
        headers=_authorization(created["session_token"]),
    )
    assert not_retryable.status_code == 409
    assert not_retryable.json()["error"]["code"] == "MESSAGE_NOT_RETRYABLE"


@pytest.mark.asyncio
async def test_invalid_expired_and_revoked_sessions(
    api_client: TestClient,
    db_session: AsyncSession,
    api_settings: Settings,
) -> None:
    invalid = api_client.get(
        "/api/v1/conversations/00000000-0000-0000-0000-000000000001/messages",
        headers=_authorization("invalid-token"),
    )
    assert invalid.status_code == 401

    expired_created = _create_conversation(api_client, name="Expired")
    revoked_created = _create_conversation(api_client, name="Revoked")
    secret = api_settings.session_token_secret.get_secret_value()
    async with db_session.begin():
        sessions = ParticipantSessionRepository(db_session)
        expired_session = await sessions.get_by_token_hash(
            hash_token(expired_created["session_token"], secret)
        )
        revoked_session = await sessions.get_by_token_hash(
            hash_token(revoked_created["session_token"], secret)
        )
        assert expired_session is not None and revoked_session is not None
        expired_session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await sessions.revoke(revoked_session)

    for created in (expired_created, revoked_created):
        response = api_client.get(
            f"/api/v1/conversations/{created['conversation']['id']}",
            headers=_authorization(created["session_token"]),
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_cross_conversation_access_is_forbidden(api_client: TestClient) -> None:
    first = _create_conversation(api_client, name="First")
    second = _create_conversation(api_client, name="Second")
    response = api_client.get(
        f"/api/v1/conversations/{second['conversation']['id']}/messages",
        headers=_authorization(first["session_token"]),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_summary_response_matches_documented_shape(
    api_client: TestClient, db_session: AsyncSession
) -> None:
    created = _create_conversation(api_client)
    conversation_id = UUID(created["conversation"]["id"])
    summary_service = SummaryService(db_session)
    summary = await summary_service.create_processing(conversation_id)
    await summary_service.mark_completed(
        summary.id,
        main_topics=["Topic"],
        agreements=["Agreement"],
        unresolved_issues=[],
        boundaries=[],
        next_steps=["Next step"],
    )
    response = api_client.get(
        f"/api/v1/conversations/{conversation_id}/summary",
        headers=_authorization(created["session_token"]),
    )
    assert response.status_code == 200
    payload = response.json()["data"]["summary"]
    assert payload["main_topics"] == ["Topic"]
    assert "completed_at" not in payload
    assert "notice" not in payload


@pytest.mark.asyncio
async def test_exception_mapping_and_undocumented_routes(
    api_client: TestClient,
    db_session: AsyncSession,
    api_settings: Settings,
) -> None:
    created = _create_conversation(api_client)
    joined = _join_conversation(api_client, created)
    conversation_id = created["conversation"]["id"]
    token = created["invitation"]["token"]

    reused = api_client.post(
        f"/api/v1/invitations/{token}/join",
        json={"display_name": "Third", "preferred_language": "en"},
    )
    assert reused.status_code == 409
    assert reused.json()["error"]["code"] == "INVITATION_ALREADY_USED"

    payload = {"client_message_id": "duplicate-id", "message": "message"}
    first = api_client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json=payload,
        headers=_authorization(joined["session_token"]),
    )
    duplicate = api_client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json=payload,
        headers=_authorization(joined["session_token"]),
    )
    assert first.status_code == 202
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "DUPLICATE_MESSAGE"

    invalid_body = api_client.post("/api/v1/conversations", json={})
    assert invalid_body.status_code == 422
    assert invalid_body.json()["error"]["code"] == "VALIDATION_ERROR"

    unsupported = api_client.post(
        "/api/v1/conversations",
        json={"display_name": "Name", "preferred_language": "xx"},
    )
    assert unsupported.status_code == 422
    assert unsupported.json()["error"]["code"] == "UNSUPPORTED_LANGUAGE"

    empty_message = api_client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"client_message_id": "empty-id", "message": "   "},
        headers=_authorization(joined["session_token"]),
    )
    assert empty_message.status_code == 422
    assert empty_message.json()["error"]["code"] == "EMPTY_MESSAGE"

    expiring = _create_conversation(api_client, name="Expiring invitation")
    invitation_secret = api_settings.invitation_token_secret.get_secret_value()
    async with db_session.begin():
        invitation = await InvitationRepository(db_session).get_by_token_hash(
            hash_token(expiring["invitation"]["token"], invitation_secret)
        )
        assert invitation is not None
        invitation.expires_at = datetime.now(UTC) - timedelta(seconds=1)

    expired_join = api_client.post(
        f"/api/v1/invitations/{expiring['invitation']['token']}/join",
        json={"display_name": "Late", "preferred_language": "en"},
    )
    assert expired_join.status_code == 410
    assert expired_join.json()["error"]["code"] == "INVITATION_EXPIRED"

    assert api_client.get("/api/v1/health").status_code == 200
    assert api_client.get("/api/v1/languages").status_code == 200
    assert api_client.get("/health").status_code == 404
    assert api_client.post("/api/v1/messages", json={}).status_code == 404
    assert (
        api_client.post(f"/api/v1/conversations/{conversation_id}/activate").status_code
        == 404
    )
