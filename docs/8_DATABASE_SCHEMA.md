# 08_DATABASE_SCHEMA.md

# Database Schema

## 1. Purpose

This document defines the database structure for the 2talk MVP.

The schema supports:

* private two-person conversations,
* secure invitation links,
* participant sessions,
* language preferences,
* original and mediated messages,
* private AI guidance,
* message-processing failures and retries,
* conversation summaries,
* privacy and authorization rules.

The schema is designed for a relational database such as PostgreSQL.

---

# 2. Core Principles

The database must preserve a strict separation between:

* original messages,
* mediated messages,
* sender guidance,
* recipient guidance,
* shared conversation content.

The other participant's original message must never be exposed through normal recipient queries.

Private guidance must always belong to one specific participant.

The database should preserve enough information to investigate technical failures without exposing sensitive data unnecessarily.

---

# 3. Entity Overview

```text
conversations
    │
    ├── invitations
    │
    ├── participants
    │       └── participant_sessions
    │
    ├── messages
    │       ├── message_deliveries
    │       ├── ai_processing_attempts
    │       └── private_guidance
    │
    └── conversation_summaries
```

---

# 4. Enumerated Values

The implementation may use native database enums or validated text columns.

## 4.1 Conversation Status

```text
waiting
active
ended
```

Meaning:

* `waiting`: Only the creator has joined.
* `active`: Two participants have joined.
* `ended`: The conversation no longer accepts messages.

---

## 4.2 Participant Role

```text
creator
invitee
```

---

## 4.3 Message Status

```text
processing
delivered
failed
blocked
```

Meaning:

* `processing`: The original message is stored and awaiting successful mediation.
* `delivered`: Mediation succeeded and the recipient may retrieve the mediated message.
* `failed`: Mediation failed and may be retried.
* `blocked`: Delivery was prevented by a safety or policy decision.

---

## 4.4 AI Processing Attempt Status

```text
started
completed
failed
rejected
```

---

## 4.5 Guidance Audience

```text
sender
recipient
```

This describes the participant's relationship to the associated message.

The database must also store the exact participant receiving the guidance.

---

## 4.6 Guidance Type

```text
communication_support
clarification
de_escalation
pause_suggestion
boundary_notice
safety_notice
```

---

## 4.7 Summary Status

```text
processing
completed
failed
```

---

# 5. Conversations Table

Stores one private conversation between a maximum of two participants.

## Table

```sql
CREATE TABLE conversations (
    id UUID PRIMARY KEY,
    title VARCHAR(150),
    description VARCHAR(1000),
    status VARCHAR(20) NOT NULL DEFAULT 'waiting',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    activated_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,

    CONSTRAINT conversations_status_check
        CHECK (status IN ('waiting', 'active', 'ended')),

    CONSTRAINT conversations_activated_state_check
        CHECK (
            activated_at IS NULL
            OR status IN ('active', 'ended')
        ),

    CONSTRAINT conversations_ended_state_check
        CHECK (
            ended_at IS NULL
            OR status = 'ended'
        )
);
```

## Notes

* `title` is optional.
* `description` is optional context supplied when the conversation is created.
* `activated_at` records when the second participant joins.
* `ended_at` records when the conversation is ended.

---

# 6. Invitations Table

Stores secure invitation tokens used by the second participant.

## Table

```sql
CREATE TABLE invitations (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL,
    token_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    used_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,

    CONSTRAINT invitations_conversation_fk
        FOREIGN KEY (conversation_id)
        REFERENCES conversations(id)
        ON DELETE CASCADE,

    CONSTRAINT invitations_token_hash_unique
        UNIQUE (token_hash)
);
```

## Security Requirement

The raw invitation token should not be stored directly.

The application should:

1. Generate a cryptographically secure random token.
2. Send the raw token to the creator once.
3. Store only a secure hash of the token.
4. Hash incoming invitation tokens before database comparison.

## Invitation Validity

An invitation is valid only when:

* `revoked_at` is null,
* `used_at` is null,
* `expires_at` is null or in the future,
* the conversation status is `waiting`,
* the conversation has fewer than two participants.

---

# 7. Participants Table

Stores the two people in each conversation.

## Table

```sql
CREATE TABLE participants (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL,
    display_name VARCHAR(80) NOT NULL,
    preferred_language VARCHAR(20) NOT NULL,
    role VARCHAR(20) NOT NULL,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT participants_conversation_fk
        FOREIGN KEY (conversation_id)
        REFERENCES conversations(id)
        ON DELETE CASCADE,

    CONSTRAINT participants_role_check
        CHECK (role IN ('creator', 'invitee')),

    CONSTRAINT participants_unique_role_per_conversation
        UNIQUE (conversation_id, role),

    CONSTRAINT participants_display_name_not_empty
        CHECK (LENGTH(TRIM(display_name)) > 0)
);
```

## Maximum Two Participants

A relational constraint alone does not conveniently enforce a maximum row count of two.

The backend must create participants inside a transaction and verify:

```sql
SELECT COUNT(*)
FROM participants
WHERE conversation_id = :conversation_id
FOR UPDATE;
```

The join operation succeeds only when the count is less than two.

The unique role constraint ensures that each conversation has at most:

* one creator,
* one invitee.

---

# 8. Participant Sessions Table

Stores temporary bearer-session credentials.

## Table

```sql
CREATE TABLE participant_sessions (
    id UUID PRIMARY KEY,
    participant_id UUID NOT NULL,
    token_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,

    CONSTRAINT participant_sessions_participant_fk
        FOREIGN KEY (participant_id)
        REFERENCES participants(id)
        ON DELETE CASCADE,

    CONSTRAINT participant_sessions_token_hash_unique
        UNIQUE (token_hash)
);
```

## Security Requirement

The raw session token must not be stored directly.

Only a secure hash should be stored.

A session is valid only when:

* `revoked_at` is null,
* `expires_at` is in the future,
* the linked participant still exists.

---

# 9. Messages Table

Stores the original message and the final mediated message.

## Table

```sql
CREATE TABLE messages (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL,
    sender_id UUID NOT NULL,
    client_message_id VARCHAR(100) NOT NULL,

    original_message TEXT NOT NULL,
    original_language VARCHAR(20),

    mediated_message TEXT,
    delivered_language VARCHAR(20),

    status VARCHAR(20) NOT NULL DEFAULT 'processing',

    communication_goal VARCHAR(100),
    detected_emotion VARCHAR(100),
    requires_pause BOOLEAN NOT NULL DEFAULT FALSE,

    failure_code VARCHAR(100),
    retry_count INTEGER NOT NULL DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    mediated_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    blocked_at TIMESTAMPTZ,

    CONSTRAINT messages_conversation_fk
        FOREIGN KEY (conversation_id)
        REFERENCES conversations(id)
        ON DELETE CASCADE,

    CONSTRAINT messages_sender_fk
        FOREIGN KEY (sender_id)
        REFERENCES participants(id)
        ON DELETE CASCADE,

    CONSTRAINT messages_status_check
        CHECK (
            status IN (
                'processing',
                'delivered',
                'failed',
                'blocked'
            )
        ),

    CONSTRAINT messages_original_not_empty
        CHECK (LENGTH(TRIM(original_message)) > 0),

    CONSTRAINT messages_retry_count_nonnegative
        CHECK (retry_count >= 0),

    CONSTRAINT messages_client_id_unique
        UNIQUE (conversation_id, sender_id, client_message_id),

    CONSTRAINT messages_delivery_content_check
        CHECK (
            status <> 'delivered'
            OR (
                mediated_message IS NOT NULL
                AND delivered_at IS NOT NULL
            )
        )
);
```

## Important Privacy Rule

`original_message` is visible only to:

* the sender,
* authorized backend processes,
* authorized system administrators under a defined operational policy.

It must never be returned to the recipient.

## Important Integrity Rule

The backend must verify that:

* `sender_id` belongs to `conversation_id`,
* the conversation is active,
* the sender is one of the two participants.

---

# 10. Message Deliveries Table

Stores recipient-specific delivery state.

Although each MVP conversation has only two participants, a delivery table makes delivery status explicit and supports future expansion.

## Table

```sql
CREATE TABLE message_deliveries (
    id UUID PRIMARY KEY,
    message_id UUID NOT NULL,
    recipient_id UUID NOT NULL,
    delivered_at TIMESTAMPTZ,
    seen_at TIMESTAMPTZ,

    CONSTRAINT message_deliveries_message_fk
        FOREIGN KEY (message_id)
        REFERENCES messages(id)
        ON DELETE CASCADE,

    CONSTRAINT message_deliveries_recipient_fk
        FOREIGN KEY (recipient_id)
        REFERENCES participants(id)
        ON DELETE CASCADE,

    CONSTRAINT message_deliveries_unique
        UNIQUE (message_id, recipient_id)
);
```

## Behaviour

A delivery row should be created only after mediation succeeds.

The recipient must be:

* a participant in the same conversation,
* different from the sender.

The backend must enforce this rule transactionally.

---

# 11. AI Processing Attempts Table

Stores each request made to the AI mediator.

This supports retries, debugging, cost tracking, and failure investigation.

## Table

```sql
CREATE TABLE ai_processing_attempts (
    id UUID PRIMARY KEY,
    message_id UUID NOT NULL,
    attempt_number INTEGER NOT NULL,
    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,
    request_started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    request_completed_at TIMESTAMPTZ,
    error_code VARCHAR(100),
    error_message TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,

    CONSTRAINT ai_processing_attempts_message_fk
        FOREIGN KEY (message_id)
        REFERENCES messages(id)
        ON DELETE CASCADE,

    CONSTRAINT ai_processing_attempts_status_check
        CHECK (
            status IN (
                'started',
                'completed',
                'failed',
                'rejected'
            )
        ),

    CONSTRAINT ai_processing_attempts_number_positive
        CHECK (attempt_number > 0),

    CONSTRAINT ai_processing_attempts_unique
        UNIQUE (message_id, attempt_number)
);
```

## Sensitive Data Rule

The full prompt and complete AI response should not be stored here by default.

The database should prefer storing:

* provider,
* model,
* status,
* timing,
* token usage,
* technical error information.

Sensitive conversation content already exists in the message records.

Duplicating it in logs increases privacy risk.

---

# 12. Private Guidance Table

Stores AI guidance that is visible to exactly one participant.

## Table

```sql
CREATE TABLE private_guidance (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL,
    message_id UUID NOT NULL,
    participant_id UUID NOT NULL,
    audience VARCHAR(20) NOT NULL,
    guidance_type VARCHAR(40) NOT NULL,
    guidance_text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    seen_at TIMESTAMPTZ,

    CONSTRAINT private_guidance_conversation_fk
        FOREIGN KEY (conversation_id)
        REFERENCES conversations(id)
        ON DELETE CASCADE,

    CONSTRAINT private_guidance_message_fk
        FOREIGN KEY (message_id)
        REFERENCES messages(id)
        ON DELETE CASCADE,

    CONSTRAINT private_guidance_participant_fk
        FOREIGN KEY (participant_id)
        REFERENCES participants(id)
        ON DELETE CASCADE,

    CONSTRAINT private_guidance_audience_check
        CHECK (audience IN ('sender', 'recipient')),

    CONSTRAINT private_guidance_type_check
        CHECK (
            guidance_type IN (
                'communication_support',
                'clarification',
                'de_escalation',
                'pause_suggestion',
                'boundary_notice',
                'safety_notice'
            )
        ),

    CONSTRAINT private_guidance_text_not_empty
        CHECK (LENGTH(TRIM(guidance_text)) > 0)
);
```

## Privacy Requirement

Guidance queries must always include:

```sql
WHERE participant_id = :authenticated_participant_id
```

The frontend must not receive all guidance and filter it locally.

## Integrity Requirement

The backend must verify that:

* the guidance participant belongs to the conversation,
* the message belongs to the same conversation,
* `audience = 'sender'` points to the message sender,
* `audience = 'recipient'` points to the other participant.

---

# 13. Conversation Summaries Table

Stores a neutral summary of the conversation.

## Table

```sql
CREATE TABLE conversation_summaries (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'processing',

    main_topics JSONB NOT NULL DEFAULT '[]'::jsonb,
    agreements JSONB NOT NULL DEFAULT '[]'::jsonb,
    unresolved_issues JSONB NOT NULL DEFAULT '[]'::jsonb,
    boundaries JSONB NOT NULL DEFAULT '[]'::jsonb,
    next_steps JSONB NOT NULL DEFAULT '[]'::jsonb,

    notice TEXT,
    failure_code VARCHAR(100),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,

    CONSTRAINT conversation_summaries_conversation_fk
        FOREIGN KEY (conversation_id)
        REFERENCES conversations(id)
        ON DELETE CASCADE,

    CONSTRAINT conversation_summaries_status_check
        CHECK (
            status IN (
                'processing',
                'completed',
                'failed'
            )
        )
);
```

## MVP Summary Rule

The MVP should normally maintain only one current summary per conversation.

This can be enforced with:

```sql
CREATE UNIQUE INDEX conversation_summaries_one_per_conversation
ON conversation_summaries(conversation_id);
```

If summary versioning is later required, remove this unique index and add:

```text
version_number
superseded_at
```

---

# 14. Optional Safety Events Table

This table is optional for the first implementation but recommended if blocked messages or safety escalations must be audited.

## Table

```sql
CREATE TABLE safety_events (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL,
    message_id UUID,
    participant_id UUID,
    category VARCHAR(100) NOT NULL,
    severity VARCHAR(30) NOT NULL,
    action_taken VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT safety_events_conversation_fk
        FOREIGN KEY (conversation_id)
        REFERENCES conversations(id)
        ON DELETE CASCADE,

    CONSTRAINT safety_events_message_fk
        FOREIGN KEY (message_id)
        REFERENCES messages(id)
        ON DELETE SET NULL,

    CONSTRAINT safety_events_participant_fk
        FOREIGN KEY (participant_id)
        REFERENCES participants(id)
        ON DELETE SET NULL
);
```

## Privacy Rule

Avoid storing unnecessary details from the original message in this table.

The event should describe the classification and system action, not duplicate the sensitive content.

---

# 15. Required Indexes

## Conversations

```sql
CREATE INDEX conversations_status_idx
ON conversations(status);
```

---

## Invitations

```sql
CREATE INDEX invitations_conversation_id_idx
ON invitations(conversation_id);

CREATE INDEX invitations_expires_at_idx
ON invitations(expires_at);
```

The unique constraint on `token_hash` automatically creates an index.

---

## Participants

```sql
CREATE INDEX participants_conversation_id_idx
ON participants(conversation_id);
```

---

## Participant Sessions

```sql
CREATE INDEX participant_sessions_participant_id_idx
ON participant_sessions(participant_id);

CREATE INDEX participant_sessions_expires_at_idx
ON participant_sessions(expires_at);
```

The unique constraint on `token_hash` automatically creates an index.

---

## Messages

```sql
CREATE INDEX messages_conversation_created_idx
ON messages(conversation_id, created_at);

CREATE INDEX messages_sender_id_idx
ON messages(sender_id);

CREATE INDEX messages_status_idx
ON messages(status);
```

---

## Message Deliveries

```sql
CREATE INDEX message_deliveries_recipient_idx
ON message_deliveries(recipient_id, delivered_at);
```

---

## AI Processing Attempts

```sql
CREATE INDEX ai_processing_attempts_message_id_idx
ON ai_processing_attempts(message_id);
```

---

## Private Guidance

```sql
CREATE INDEX private_guidance_participant_created_idx
ON private_guidance(participant_id, created_at);

CREATE INDEX private_guidance_message_id_idx
ON private_guidance(message_id);
```

---

## Conversation Summaries

```sql
CREATE INDEX conversation_summaries_status_idx
ON conversation_summaries(status);
```

---

# 16. Transaction Requirements

Several operations must be performed inside database transactions.

## 16.1 Create Conversation

The following should succeed or fail together:

1. Create the conversation.
2. Create the creator participant.
3. Create the invitation.
4. Create the participant session.

---

## 16.2 Join Conversation

The following should succeed or fail together:

1. Lock the conversation or participant set.
2. Confirm the room is not full.
3. Confirm the invitation is valid.
4. Create the invitee participant.
5. Mark the invitation as used.
6. Change conversation status to `active`.
7. Set `activated_at`.
8. Create the invitee session.

This transaction prevents two people from joining simultaneously as the second participant.

---

## 16.3 Submit Message

The initial transaction should:

1. Confirm the participant belongs to the active conversation.
2. Confirm the client message ID is not duplicated.
3. Store the original message.
4. Set message status to `processing`.
5. Create the first AI-processing attempt.

The AI request itself should not hold a long-running database transaction open.

---

## 16.4 Complete Mediation

After a valid AI response is received, one transaction should:

1. Store the mediated message.
2. Store language and mediation metadata.
3. Create private guidance records.
4. Create the recipient delivery record.
5. Mark the AI attempt as completed.
6. Change message status to `delivered`.
7. Set `mediated_at`.
8. Set `delivered_at`.

The recipient must not see a partially completed delivery.

---

## 16.5 Failed Mediation

One transaction should:

1. Mark the current AI attempt as failed.
2. Store a technical failure code.
3. Change the message status to `failed`.
4. Leave the delivery record absent.

The original message must remain available for retry by the sender.

---

## 16.6 End Conversation

One transaction should:

1. Change status to `ended`.
2. Set `ended_at`.
3. Prevent future message creation.
4. Optionally create a summary record with status `processing`.

---

# 17. Query Privacy Rules

## 17.1 Outgoing Message Query

When a participant requests their own outgoing messages, the backend may return:

```text
original_message
mediated_message
status
private guidance addressed to that participant
```

---

## 17.2 Incoming Message Query

When a participant requests incoming messages, the backend may return:

```text
mediated_message
sender display name
delivery timestamps
private guidance addressed to the authenticated recipient
```

It must never return:

```text
original_message
sender-only guidance
internal AI metadata
```

---

## 17.3 Recommended Message Query Pattern

A recipient-safe query should explicitly choose columns rather than use:

```sql
SELECT *
```

Example:

```sql
SELECT
    m.id,
    m.sender_id,
    p.display_name AS sender_display_name,
    m.mediated_message,
    m.delivered_language,
    m.status,
    m.created_at,
    m.delivered_at
FROM messages m
JOIN participants p
    ON p.id = m.sender_id
JOIN message_deliveries d
    ON d.message_id = m.id
WHERE
    m.conversation_id = :conversation_id
    AND d.recipient_id = :authenticated_participant_id
    AND m.status = 'delivered'
ORDER BY m.created_at ASC;
```

Using explicit column selection reduces the risk of accidentally exposing `original_message`.

---

# 18. Deletion and Retention

The MVP must define a retention policy before public deployment.

Possible later options include:

* automatic deletion after a fixed period,
* participant-requested conversation deletion,
* deletion after both participants agree,
* limited retention of technical logs,
* anonymized product analytics.

Until a policy is finalized:

* do not implement indefinite retention casually,
* do not delete conversations automatically without documented behaviour,
* do not use private message content for model training,
* do not copy conversation content into unnecessary analytics systems.

---

# 19. Encryption and Sensitive Data

The production database should use encryption at rest.

Transport between application and database must use encrypted connections.

The following values require special protection:

* original messages,
* mediated messages,
* private guidance,
* conversation summaries,
* invitation tokens,
* participant session tokens.

Raw invitation and session tokens must never be stored.

Application logs must not contain:

* raw bearer tokens,
* raw invitation tokens,
* full original messages by default,
* private guidance,
* database credentials,
* OpenAI API keys.

---

# 20. Database-Level Definition of Done

The database implementation is complete for the MVP when:

* conversations support exactly one creator and one invitee,
* secure invitation hashes are stored,
* secure participant-session hashes are stored,
* duplicate client messages are prevented,
* original and mediated messages are stored separately,
* recipients cannot retrieve original messages,
* private guidance belongs to one exact participant,
* failed AI processing creates no recipient delivery,
* retry attempts are recorded,
* ended conversations reject new messages,
* summaries are stored in a structured format,
* required indexes exist,
* join and delivery operations use transactions,
* foreign keys and integrity checks are enforced.
