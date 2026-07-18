# 07_API_SPEC.md

# API Specification

## 1. Purpose

This document defines the backend API for the 2talk MVP.

The API supports:

* creating a private conversation,
* joining through an invitation link,
* identifying the two participants,
* sending messages for AI mediation,
* retrieving mediated conversation history,
* retrieving private AI guidance,
* ending a conversation,
* generating a neutral conversation summary.

The API must never expose one participant's raw messages or private guidance to the other participant.

---

# 2. General Principles

## 2.1 Base Path

All API endpoints should use the following base path:

```text
/api/v1
```

Example:

```text
POST /api/v1/conversations
```

---

## 2.2 Data Format

All requests and responses use JSON unless otherwise specified.

Request header:

```http
Content-Type: application/json
```

Response header:

```http
Content-Type: application/json
```

---

## 2.3 Authentication Model

The MVP does not require permanent user accounts.

Access is based on:

* a secure invitation token,
* a participant session token,
* the participant's assigned identity within the conversation.

After a participant creates or joins a conversation, the backend returns a participant session token.

That token must be included in protected requests.

Example:

```http
Authorization: Bearer <participant_session_token>
```

The backend must validate that the participant belongs to the requested conversation.

---

## 2.4 Time Format

All timestamps use ISO 8601 in UTC.

Example:

```text
2026-07-18T12:30:00Z
```

---

## 2.5 Identifier Format

Identifiers should be non-sequential and difficult to guess.

The API may use UUIDs or another secure identifier format.

Examples:

```text
conversation_id
participant_id
message_id
guidance_id
summary_id
```

---

# 3. Standard Response Structure

## 3.1 Successful Response

A successful request returns:

```json
{
  "success": true,
  "data": {}
}
```

---

## 3.2 Error Response

An unsuccessful request returns:

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable explanation."
  }
}
```

Optional field:

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request contains invalid fields.",
    "details": {
      "display_name": "Display name is required."
    }
  }
}
```

---

# 4. Conversation Endpoints

## 4.1 Create Conversation

Creates a new private conversation and registers the creator as Participant A.

### Endpoint

```http
POST /api/v1/conversations
```

### Authentication

Not required.

### Request

```json
{
  "title": "Family discussion",
  "display_name": "Anna",
  "preferred_language": "sv",
  "description": "We want to discuss an ongoing misunderstanding."
}
```

### Fields

| Field                | Required | Description                        |
| -------------------- | -------: | ---------------------------------- |
| `title`              |       No | Optional conversation title        |
| `display_name`       |      Yes | Creator's display name             |
| `preferred_language` |      Yes | Creator's preferred language code  |
| `description`        |       No | Short context for the conversation |

### Successful Response

```json
{
  "success": true,
  "data": {
    "conversation": {
      "id": "conv_7f2a91",
      "title": "Family discussion",
      "description": "We want to discuss an ongoing misunderstanding.",
      "status": "waiting",
      "created_at": "2026-07-18T12:30:00Z"
    },
    "participant": {
      "id": "part_a81d2e",
      "display_name": "Anna",
      "preferred_language": "sv",
      "role": "creator"
    },
    "invitation": {
      "token": "secure_invitation_token",
      "url": "https://2talk.org/join/secure_invitation_token"
    },
    "session_token": "participant_session_token"
  }
}
```

### Validation Rules

* `display_name` must not be empty.
* `preferred_language` must be supported.
* `title` and `description` must respect length limits.
* Input must be sanitized and validated.

### Error Codes

```text
VALIDATION_ERROR
UNSUPPORTED_LANGUAGE
RATE_LIMITED
INTERNAL_ERROR
```

---

## 4.2 Get Conversation

Returns the conversation state for the authenticated participant.

### Endpoint

```http
GET /api/v1/conversations/{conversation_id}
```

### Authentication

Required.

### Successful Response

```json
{
  "success": true,
  "data": {
    "conversation": {
      "id": "conv_7f2a91",
      "title": "Family discussion",
      "description": "We want to discuss an ongoing misunderstanding.",
      "status": "active",
      "created_at": "2026-07-18T12:30:00Z",
      "ended_at": null
    },
    "current_participant": {
      "id": "part_a81d2e",
      "display_name": "Anna",
      "preferred_language": "sv"
    },
    "other_participant": {
      "id": "part_2c419f",
      "display_name": "John",
      "preferred_language": "en"
    }
  }
}
```

### Privacy Requirements

The response must not include:

* the other participant's session token,
* raw messages written by the other participant,
* private guidance addressed to the other participant,
* internal AI analysis.

### Error Codes

```text
UNAUTHORIZED
FORBIDDEN
CONVERSATION_NOT_FOUND
INTERNAL_ERROR
```

---

## 4.3 End Conversation

Ends an active conversation.

### Endpoint

```http
POST /api/v1/conversations/{conversation_id}/end
```

### Authentication

Required.

### Request

```json
{
  "generate_summary": true
}
```

### Successful Response

```json
{
  "success": true,
  "data": {
    "conversation": {
      "id": "conv_7f2a91",
      "status": "ended",
      "ended_at": "2026-07-18T13:45:00Z"
    },
    "summary_status": "processing"
  }
}
```

### Behaviour

* The conversation status changes to `ended`.
* New messages are rejected.
* Existing history remains available.
* A summary may be generated if requested.
* Ending a conversation must not delete its content automatically.

### Error Codes

```text
UNAUTHORIZED
FORBIDDEN
CONVERSATION_NOT_FOUND
CONVERSATION_ALREADY_ENDED
INTERNAL_ERROR
```

---

# 5. Invitation Endpoints

## 5.1 Validate Invitation

Checks whether an invitation link is valid before showing the join form.

### Endpoint

```http
GET /api/v1/invitations/{invitation_token}
```

### Authentication

Not required.

### Successful Response

```json
{
  "success": true,
  "data": {
    "valid": true,
    "conversation": {
      "title": "Family discussion",
      "status": "waiting"
    }
  }
}
```

### Invalid Response

```json
{
  "success": false,
  "error": {
    "code": "INVALID_INVITATION",
    "message": "This invitation is invalid or no longer available."
  }
}
```

### Privacy Requirements

Before joining, the response must not expose:

* participant identities,
* conversation messages,
* private descriptions not intended for invitees,
* internal identifiers beyond what is necessary.

### Error Codes

```text
INVALID_INVITATION
INVITATION_EXPIRED
CONVERSATION_FULL
CONVERSATION_ENDED
INTERNAL_ERROR
```

---

## 5.2 Join Conversation

Registers the second participant.

### Endpoint

```http
POST /api/v1/invitations/{invitation_token}/join
```

### Authentication

Not required.

### Request

```json
{
  "display_name": "John",
  "preferred_language": "en"
}
```

### Successful Response

```json
{
  "success": true,
  "data": {
    "conversation": {
      "id": "conv_7f2a91",
      "title": "Family discussion",
      "status": "active"
    },
    "participant": {
      "id": "part_2c419f",
      "display_name": "John",
      "preferred_language": "en",
      "role": "invitee"
    },
    "session_token": "participant_session_token"
  }
}
```

### Behaviour

* Only one second participant may join.
* When the second participant joins, the conversation status changes from `waiting` to `active`.
* The invitation cannot be used to create a third participant.

### Error Codes

```text
VALIDATION_ERROR
INVALID_INVITATION
INVITATION_EXPIRED
CONVERSATION_FULL
CONVERSATION_ENDED
UNSUPPORTED_LANGUAGE
INTERNAL_ERROR
```

---

# 6. Participant Endpoints

## 6.1 Update Preferred Language

Updates the authenticated participant's preferred language.

### Endpoint

```http
PATCH /api/v1/conversations/{conversation_id}/participants/me
```

### Authentication

Required.

### Request

```json
{
  "preferred_language": "fa"
}
```

### Successful Response

```json
{
  "success": true,
  "data": {
    "participant": {
      "id": "part_a81d2e",
      "display_name": "Anna",
      "preferred_language": "fa"
    }
  }
}
```

### Behaviour

* The new language applies to future mediated messages.
* Existing delivered messages do not need to be retranslated in the MVP.
* The participant may only update their own settings.

### Error Codes

```text
VALIDATION_ERROR
UNSUPPORTED_LANGUAGE
UNAUTHORIZED
FORBIDDEN
CONVERSATION_NOT_FOUND
INTERNAL_ERROR
```

---

# 7. Message Endpoints

## 7.1 Send Message

Submits a raw message for AI mediation.

### Endpoint

```http
POST /api/v1/conversations/{conversation_id}/messages
```

### Authentication

Required.

### Request

```json
{
  "client_message_id": "client_91cd73",
  "message": "You never listen to anything I say."
}
```

### Fields

| Field               | Required | Description                                            |
| ------------------- | -------: | ------------------------------------------------------ |
| `client_message_id` |      Yes | Client-generated identifier used to prevent duplicates |
| `message`           |      Yes | Raw message written by the sender                      |

### Immediate Successful Response

```json
{
  "success": true,
  "data": {
    "message": {
      "id": "msg_52df19",
      "client_message_id": "client_91cd73",
      "status": "processing",
      "created_at": "2026-07-18T12:40:00Z"
    }
  }
}
```

### Completed Message Response

After mediation succeeds, the sender may retrieve:

```json
{
  "success": true,
  "data": {
    "message": {
      "id": "msg_52df19",
      "sender_id": "part_a81d2e",
      "sender_display_name": "Anna",
      "original_message": "You never listen to anything I say.",
      "mediated_message": "I feel unheard and frustrated because I do not feel that my concerns are being acknowledged.",
      "status": "delivered",
      "created_at": "2026-07-18T12:40:00Z",
      "delivered_at": "2026-07-18T12:40:03Z"
    },
    "private_guidance": {
      "id": "guide_5b01e8",
      "text": "Your frustration has been preserved while removing the personal attack."
    }
  }
}
```

### Recipient Version

The recipient must receive a different response representation:

```json
{
  "success": true,
  "data": {
    "message": {
      "id": "msg_52df19",
      "sender_id": "part_a81d2e",
      "sender_display_name": "Anna",
      "mediated_message": "I feel unheard and frustrated because I do not feel that my concerns are being acknowledged.",
      "delivered_language": "en",
      "status": "delivered",
      "created_at": "2026-07-18T12:40:00Z",
      "delivered_at": "2026-07-18T12:40:03Z"
    }
  }
}
```

The recipient response must never include `original_message`.

### Processing Behaviour

The backend must:

1. Validate the participant and conversation.
2. Reject messages in ended conversations.
3. Store the raw message securely.
4. Send the necessary context to the AI mediator.
5. Validate the structured AI response.
6. Store the mediated message.
7. Store private guidance separately.
8. Mark the message as delivered.
9. Notify the recipient.

### Message Status Values

```text
processing
delivered
failed
blocked
```

### Error Codes

```text
VALIDATION_ERROR
EMPTY_MESSAGE
MESSAGE_TOO_LONG
UNAUTHORIZED
FORBIDDEN
CONVERSATION_NOT_FOUND
CONVERSATION_NOT_ACTIVE
DUPLICATE_MESSAGE
AI_PROCESSING_FAILED
AI_RESPONSE_INVALID
RATE_LIMITED
INTERNAL_ERROR
```

---

## 7.2 Get Conversation Messages

Returns messages visible to the authenticated participant.

### Endpoint

```http
GET /api/v1/conversations/{conversation_id}/messages
```

### Authentication

Required.

### Query Parameters

```text
after=<message_id>
limit=50
```

Example:

```http
GET /api/v1/conversations/conv_7f2a91/messages?after=msg_52df19&limit=50
```

### Successful Response

```json
{
  "success": true,
  "data": {
    "messages": [
      {
        "id": "msg_52df19",
        "sender_id": "part_a81d2e",
        "sender_display_name": "Anna",
        "direction": "outgoing",
        "original_message": "You never listen to anything I say.",
        "mediated_message": "I feel unheard and frustrated because I do not feel that my concerns are being acknowledged.",
        "status": "delivered",
        "created_at": "2026-07-18T12:40:00Z",
        "delivered_at": "2026-07-18T12:40:03Z"
      },
      {
        "id": "msg_912fac",
        "sender_id": "part_2c419f",
        "sender_display_name": "John",
        "direction": "incoming",
        "mediated_message": "I did not realize you felt ignored. I would like to understand which concern I missed.",
        "status": "delivered",
        "created_at": "2026-07-18T12:42:00Z",
        "delivered_at": "2026-07-18T12:42:02Z"
      }
    ],
    "has_more": false,
    "next_cursor": null
  }
}
```

### Privacy Behaviour

For outgoing messages, the authenticated sender may receive:

* their own raw message,
* their own mediated message,
* their own private guidance.

For incoming messages, they may receive:

* only the mediated message,
* guidance addressed specifically to them.

They must not receive:

* the other participant's raw message,
* the other participant's private guidance,
* hidden AI reasoning or internal analysis.

### Error Codes

```text
UNAUTHORIZED
FORBIDDEN
CONVERSATION_NOT_FOUND
INVALID_CURSOR
INTERNAL_ERROR
```

---

## 7.3 Get Message Status

Returns the processing status of a submitted message.

### Endpoint

```http
GET /api/v1/conversations/{conversation_id}/messages/{message_id}
```

### Authentication

Required.

### Processing Response

```json
{
  "success": true,
  "data": {
    "message": {
      "id": "msg_52df19",
      "status": "processing",
      "created_at": "2026-07-18T12:40:00Z"
    }
  }
}
```

### Failed Response

```json
{
  "success": true,
  "data": {
    "message": {
      "id": "msg_52df19",
      "status": "failed",
      "failure_code": "AI_PROCESSING_FAILED",
      "retry_allowed": true
    }
  }
}
```

### Error Codes

```text
UNAUTHORIZED
FORBIDDEN
MESSAGE_NOT_FOUND
INTERNAL_ERROR
```

---

## 7.4 Retry Failed Message

Retries AI mediation for a message that was stored but not delivered.

### Endpoint

```http
POST /api/v1/conversations/{conversation_id}/messages/{message_id}/retry
```

### Authentication

Required.

### Request

No body required.

### Successful Response

```json
{
  "success": true,
  "data": {
    "message": {
      "id": "msg_52df19",
      "status": "processing"
    }
  }
}
```

### Behaviour

* Only the original sender may retry the message.
* Delivered or blocked messages cannot be retried.
* Retrying must not create a duplicate message.
* The recipient must not see the message until mediation succeeds.

### Error Codes

```text
UNAUTHORIZED
FORBIDDEN
MESSAGE_NOT_FOUND
MESSAGE_NOT_RETRYABLE
CONVERSATION_NOT_ACTIVE
INTERNAL_ERROR
```

---

# 8. Private Guidance Endpoints

## 8.1 Get Private Guidance

Returns guidance addressed only to the authenticated participant.

### Endpoint

```http
GET /api/v1/conversations/{conversation_id}/guidance
```

### Authentication

Required.

### Query Parameters

```text
after=<guidance_id>
limit=50
```

### Successful Response

```json
{
  "success": true,
  "data": {
    "guidance": [
      {
        "id": "guide_5b01e8",
        "message_id": "msg_52df19",
        "audience": "sender",
        "text": "Your frustration has been preserved while removing the personal attack.",
        "type": "communication_support",
        "created_at": "2026-07-18T12:40:03Z"
      },
      {
        "id": "guide_a902d4",
        "message_id": "msg_912fac",
        "audience": "recipient",
        "text": "The other participant appears frustrated. Acknowledging the concern before explaining your position may help.",
        "type": "de_escalation",
        "created_at": "2026-07-18T12:42:02Z"
      }
    ]
  }
}
```

### Guidance Types

```text
communication_support
clarification
de_escalation
pause_suggestion
boundary_notice
safety_notice
```

### Privacy Requirements

* A participant may retrieve only guidance addressed to them.
* Guidance for the other participant must not be returned.
* Client-side filtering is not sufficient; backend authorization is required.

### Error Codes

```text
UNAUTHORIZED
FORBIDDEN
CONVERSATION_NOT_FOUND
INVALID_CURSOR
INTERNAL_ERROR
```

---

# 9. Summary Endpoints

## 9.1 Generate Conversation Summary

Requests a neutral AI-generated summary.

### Endpoint

```http
POST /api/v1/conversations/{conversation_id}/summary
```

### Authentication

Required.

### Request

```json
{
  "include_next_steps": true
}
```

### Successful Response

```json
{
  "success": true,
  "data": {
    "summary": {
      "id": "sum_82bd14",
      "status": "processing",
      "created_at": "2026-07-18T13:45:00Z"
    }
  }
}
```

### Behaviour

The summary should be based on mediated conversation content and must:

* remain neutral,
* identify major topics,
* identify explicit points of agreement,
* identify unresolved disagreements,
* preserve stated boundaries,
* avoid inventing decisions or commitments,
* avoid declaring a winner.

### Error Codes

```text
UNAUTHORIZED
FORBIDDEN
CONVERSATION_NOT_FOUND
INSUFFICIENT_CONTENT
SUMMARY_ALREADY_PROCESSING
AI_PROCESSING_FAILED
INTERNAL_ERROR
```

---

## 9.2 Get Conversation Summary

Returns the summary visible to both participants.

### Endpoint

```http
GET /api/v1/conversations/{conversation_id}/summary
```

### Authentication

Required.

### Successful Response

```json
{
  "success": true,
  "data": {
    "summary": {
      "id": "sum_82bd14",
      "status": "completed",
      "main_topics": [
        "Feeling unheard",
        "Expectations about communication"
      ],
      "agreements": [
        "Both participants want clearer communication."
      ],
      "unresolved_issues": [
        "They have not agreed on how often they should discuss the issue."
      ],
      "boundaries": [
        "One participant requested a pause before continuing."
      ],
      "next_steps": [
        "Resume the discussion only when both participants are ready."
      ],
      "created_at": "2026-07-18T13:45:05Z"
    }
  }
}
```

### Insufficient Content Response

```json
{
  "success": true,
  "data": {
    "summary": {
      "status": "completed",
      "main_topics": [],
      "agreements": [],
      "unresolved_issues": [],
      "boundaries": [],
      "next_steps": [],
      "notice": "There was not enough meaningful conversation to create a detailed summary."
    }
  }
}
```

### Error Codes

```text
UNAUTHORIZED
FORBIDDEN
CONVERSATION_NOT_FOUND
SUMMARY_NOT_FOUND
INTERNAL_ERROR
```

---

# 10. Real-Time Events

The MVP should provide real-time or near-real-time updates.

The implementation may use:

* Server-Sent Events,
* WebSockets,
* short polling.

The exact transport may be chosen during implementation.

## Suggested Event Endpoint

```http
GET /api/v1/conversations/{conversation_id}/events
```

### Authentication

Required.

### Suggested Event Types

```text
participant_joined
conversation_activated
message_processing
message_delivered
message_failed
guidance_created
conversation_ended
summary_ready
```

### Example Event

```json
{
  "event": "message_delivered",
  "data": {
    "message_id": "msg_52df19",
    "conversation_id": "conv_7f2a91",
    "delivered_at": "2026-07-18T12:40:03Z"
  }
}
```

### Privacy Requirement

Event payloads must follow the same privacy rules as normal API responses.

A recipient must never receive another participant's raw message or private guidance through a real-time event.

---

# 11. Supported Languages Endpoint

## 11.1 List Supported Languages

Returns languages available in the MVP.

### Endpoint

```http
GET /api/v1/languages
```

### Authentication

Not required.

### Successful Response

```json
{
  "success": true,
  "data": {
    "languages": [
      {
        "code": "en",
        "name": "English"
      },
      {
        "code": "sv",
        "name": "Swedish"
      },
      {
        "code": "fa",
        "name": "Persian"
      }
    ]
  }
}
```

The final supported-language list may be defined during implementation.

The backend must validate language codes rather than trusting arbitrary client input.

---

# 12. Health Endpoint

## 12.1 Service Health

Provides a minimal system-health response for deployment checks.

### Endpoint

```http
GET /api/v1/health
```

### Authentication

Not required.

### Successful Response

```json
{
  "success": true,
  "data": {
    "status": "ok",
    "timestamp": "2026-07-18T12:30:00Z"
  }
}
```

The public health endpoint must not expose:

* API keys,
* database credentials,
* detailed internal errors,
* software secrets,
* private user information.

---

# 13. HTTP Status Codes

Recommended status codes:

| Status | Meaning                                          |
| -----: | ------------------------------------------------ |
|  `200` | Request completed successfully                   |
|  `201` | Resource created successfully                    |
|  `202` | Request accepted for asynchronous processing     |
|  `400` | Invalid request                                  |
|  `401` | Authentication required or invalid               |
|  `403` | Authenticated but not permitted                  |
|  `404` | Resource not found                               |
|  `409` | Conflict, duplicate, full room, or invalid state |
|  `422` | Valid JSON but unacceptable field values         |
|  `429` | Rate limit exceeded                              |
|  `500` | Internal server error                            |
|  `502` | External AI service returned an invalid response |
|  `503` | Service temporarily unavailable                  |

---

# 14. Rate Limiting

The backend should apply reasonable rate limits to:

* conversation creation,
* invitation validation,
* joining attempts,
* message sending,
* AI mediation requests,
* summary generation.

Rate limiting must not expose whether a private conversation exists.

Example response:

```json
{
  "success": false,
  "error": {
    "code": "RATE_LIMITED",
    "message": "Too many requests. Please try again later."
  }
}
```

---

# 15. Input Limits

Recommended initial limits:

| Input                    |  Suggested limit |
| ------------------------ | ---------------: |
| Display name             |    80 characters |
| Conversation title       |   150 characters |
| Conversation description | 1,000 characters |
| Message                  | 5,000 characters |

The final values may be adjusted during implementation.

The backend must enforce limits independently of the frontend.

---

# 16. Data Exposure Rules

The API must enforce the following rules:

## A participant may access:

* their own participant profile,
* the other participant's display name and preferred language,
* their own raw outgoing messages,
* mediated messages sent in both directions,
* private guidance addressed to them,
* shared conversation summaries.

## A participant may not access:

* the other participant's raw messages,
* the other participant's private guidance,
* the other participant's session token,
* internal AI reasoning,
* hidden safety classifications unless the interface explicitly requires them,
* server logs,
* API credentials.

These rules must be enforced on the backend.

---

# 17. MVP Endpoint Summary

```text
POST   /api/v1/conversations
GET    /api/v1/conversations/{conversation_id}
POST   /api/v1/conversations/{conversation_id}/end

GET    /api/v1/invitations/{invitation_token}
POST   /api/v1/invitations/{invitation_token}/join

PATCH  /api/v1/conversations/{conversation_id}/participants/me

POST   /api/v1/conversations/{conversation_id}/messages
GET    /api/v1/conversations/{conversation_id}/messages
GET    /api/v1/conversations/{conversation_id}/messages/{message_id}
POST   /api/v1/conversations/{conversation_id}/messages/{message_id}/retry

GET    /api/v1/conversations/{conversation_id}/guidance

POST   /api/v1/conversations/{conversation_id}/summary
GET    /api/v1/conversations/{conversation_id}/summary

GET    /api/v1/conversations/{conversation_id}/events

GET    /api/v1/languages
GET    /api/v1/health
```

---

# 18. Definition of API Completion

The API is complete for the MVP when:

* a conversation can be created,
* a second participant can join securely,
* a third participant is rejected,
* participant language preferences are stored,
* every message passes through AI mediation,
* failed mediation never exposes the raw message,
* the recipient receives only the mediated version,
* private guidance is visible only to its intended participant,
* messages update without manual refresh,
* conversations can be ended,
* neutral summaries can be generated,
* all authorization and privacy acceptance tests pass.
