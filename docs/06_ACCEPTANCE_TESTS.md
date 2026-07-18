# 06_ACCEPTANCE_TESTS.md

# Acceptance Tests

## 1. Purpose

This document defines the conditions that the 2talk MVP must satisfy before it can be considered complete.

The tests focus on the core product promise:

> Two people should be able to communicate through AI mediation with clearer meaning, reduced unnecessary conflict, and automatic translation when needed.

Each test should be marked as:

* **Pass**
* **Fail**
* **Not tested**

The MVP is ready only when all critical tests pass.

---

# 2. Conversation Creation

## AT-01 — Create a private conversation

**Given** a user is on the landing page
**When** the user selects Create Conversation and enters the required information
**Then** the system creates a new private conversation room.

### Pass criteria

* A unique conversation is created.
* The creator becomes the first participant.
* The conversation status is active.
* A secure invitation link is generated.

**Priority:** Critical

---

## AT-02 — Optional conversation title

**Given** a user creates a conversation
**When** the title field is left empty
**Then** the conversation should still be created successfully.

### Pass criteria

* The conversation does not require a title.
* The interface displays a suitable default label if needed.

**Priority:** Normal

---

## AT-03 — Invalid conversation creation

**Given** a user attempts to create a conversation
**When** required information is missing or invalid
**Then** the system rejects the request and explains what must be corrected.

### Pass criteria

* No incomplete conversation is created.
* The user receives a clear validation message.
* Previously entered valid information is not unnecessarily lost.

**Priority:** Critical

---

# 3. Invitation and Joining

## AT-04 — Generate an invitation link

**Given** a conversation has been created
**When** the creator views the invitation option
**Then** the system provides a unique invitation link.

### Pass criteria

* The link belongs only to that conversation.
* The invitation token is difficult to guess.
* The link can be copied and shared.

**Priority:** Critical

---

## AT-05 — Join as the second participant

**Given** a valid invitation link exists
**When** another person opens it and enters a display name and preferred language
**Then** that person joins as the second participant.

### Pass criteria

* The second participant is added to the correct conversation.
* Both participants can see that the room is ready.
* The second participant cannot access another conversation through the same link.

**Priority:** Critical

---

## AT-06 — Prevent a third participant

**Given** two participants have already joined a conversation
**When** a third person opens the invitation link
**Then** the system does not allow them to join.

### Pass criteria

* The conversation remains limited to two participants.
* The third person receives a clear message that the room is full or closed.
* No participant data is exposed.

**Priority:** Critical

---

## AT-07 — Reject invalid invitation links

**Given** a person opens an invalid, expired, or altered invitation link
**When** the system checks the invitation
**Then** access is denied.

### Pass criteria

* The person cannot view the conversation.
* The system does not reveal whether a specific conversation exists.
* A clear error message is shown.

**Priority:** Critical

---

# 4. Language Selection

## AT-08 — Select a preferred language

**Given** a participant creates or joins a conversation
**When** they select a preferred language
**Then** that language is stored for the participant.

### Pass criteria

* Each participant may choose a different language.
* The selected language remains active during the conversation.
* The participant can see which language they selected.

**Priority:** Critical

---

## AT-09 — Translate between two languages

**Given** Participant A uses Swedish and Participant B uses English
**When** Participant A sends a Swedish message
**Then** Participant B receives the mediated message in English.

### Pass criteria

* The recipient receives understandable English.
* The essential meaning is preserved.
* Unnecessary hostility is reduced before or during translation.
* The raw Swedish message is not displayed to Participant B.

**Priority:** Critical

---

## AT-10 — Translate in both directions

**Given** two participants use different languages
**When** each participant sends messages
**Then** mediation and translation work correctly in both directions.

### Pass criteria

* Each participant writes in their own language.
* Each participant receives messages in their selected language.
* The system does not require manual translation.

**Priority:** Critical

---

## AT-11 — Same-language conversation

**Given** both participants select the same language
**When** they exchange messages
**Then** the AI mediates the conversation without unnecessary translation.

### Pass criteria

* The mediated message remains in the shared language.
* The wording sounds natural.
* The essential meaning remains unchanged.

**Priority:** Critical

---

# 5. Message Mediation

## AT-12 — Every message passes through mediation

**Given** a participant submits a message
**When** the message is sent
**Then** the system processes it through the AI before delivery.

### Pass criteria

* The raw message is not delivered directly.
* A mediated version is generated.
* The mediated version is stored.
* Only the mediated version is visible to the recipient.

**Priority:** Critical

---

## AT-13 — Preserve neutral meaning

**Given** a participant sends a clear, neutral message
**When** the AI mediates it
**Then** the meaning remains substantially unchanged.

### Example

**Original:**

> I will arrive at six o'clock.

**Acceptable mediated result:**

> I will arrive at 6:00.

### Pass criteria

* No unnecessary emotion is added.
* No factual information is changed.
* The message is not made longer without reason.

**Priority:** Critical

---

## AT-14 — Reduce unnecessary hostility

**Given** a participant sends an insulting or aggressive message
**When** the AI mediates it
**Then** the unnecessary attack is reduced while the complaint or boundary remains clear.

### Example

**Original:**

> You are an idiot. You never listen to anything I say.

**Acceptable mediated result:**

> The other participant feels unheard and is frustrated that their concerns have not been acknowledged.

### Pass criteria

* Direct humiliation is not passed to the recipient.
* The sender's frustration remains understandable.
* The central complaint is preserved.
* The AI does not invent forgiveness or reconciliation.

**Priority:** Critical

---

## AT-15 — Preserve rejection

**Given** a participant clearly rejects a request or proposal
**When** the AI mediates the message
**Then** the rejection remains clear.

### Example

**Original:**

> No. I do not want to meet you.

**Acceptable mediated result:**

> The other participant does not want to meet.

### Pass criteria

* “No” does not become “maybe.”
* The AI does not add future possibility.
* The recipient cannot reasonably misunderstand the rejection.

**Priority:** Critical

---

## AT-16 — Preserve a request for space

**Given** a participant asks to stop or pause communication
**When** the AI mediates the message
**Then** the request remains direct and unmistakable.

### Example

**Original:**

> Leave me alone. I do not want to talk right now.

**Acceptable mediated result:**

> The other participant is asking for space and does not want to continue the conversation right now.

### Pass criteria

* The boundary is not weakened.
* The AI does not encourage the recipient to continue messaging.
* The AI may privately suggest respecting the request.

**Priority:** Critical

---

## AT-17 — Do not invent emotional meaning

**Given** a message does not express affection, forgiveness, regret, or hope
**When** the AI mediates it
**Then** those emotions are not added.

### Example

**Original:**

> I need time to think.

**Unacceptable result:**

> They still care about you but need some time.

### Pass criteria

* Unsupported emotions are not introduced.
* Hidden intentions are not claimed as fact.
* Uncertainty remains uncertainty.

**Priority:** Critical

---

## AT-18 — Preserve factual disagreement

**Given** two participants disagree about a fact or decision
**When** the AI mediates their messages
**Then** the disagreement remains visible.

### Pass criteria

* The AI does not force artificial agreement.
* The AI does not choose which participant is correct.
* The message remains understandable and respectful.

**Priority:** Critical

---

## AT-19 — Avoid over-softening

**Given** a participant communicates a serious complaint
**When** the AI mediates it
**Then** the message does not become so vague or polite that the complaint disappears.

### Pass criteria

* The recipient can still understand what is wrong.
* The seriousness of the issue is preserved.
* The AI improves delivery rather than erasing the problem.

**Priority:** Critical

---

# 6. Context and Misunderstanding

## AT-20 — Use conversation context

**Given** a message refers to an earlier part of the discussion
**When** the AI mediates it
**Then** the response reflects the relevant conversation history.

### Pass criteria

* Pronouns and references are interpreted using prior messages when reasonably possible.
* The AI does not treat each message as an isolated statement.
* Earlier boundaries and decisions are not forgotten.

**Priority:** Critical

---

## AT-21 — Detect likely misunderstanding

**Given** the participants appear to interpret the same statement differently
**When** the AI processes the next message
**Then** it may identify and clarify the likely misunderstanding.

### Pass criteria

* The clarification is neutral.
* Neither participant is blamed.
* The AI does not interrupt when no meaningful misunderstanding exists.
* The clarification helps the conversation continue.

**Priority:** Normal

---

## AT-22 — Handle ambiguous messages carefully

**Given** a message has more than one reasonable interpretation
**When** the AI processes it
**Then** it does not confidently invent a hidden meaning.

### Pass criteria

* The mediated message stays close to what is explicit.
* Private guidance may note the ambiguity.
* The system may ask the sender to clarify when necessary.

**Priority:** Critical

---

# 7. Private AI Guidance

## AT-23 — Sender guidance remains private

**Given** the AI generates advice for the sender
**When** the message is processed
**Then** only the sender can see that guidance.

### Pass criteria

* The recipient cannot retrieve or view sender guidance.
* Guidance is clearly separated from the delivered message.
* Guidance is not inserted into the public conversation history.

**Priority:** Critical

---

## AT-24 — Recipient guidance remains private

**Given** the AI generates advice for the recipient
**When** the mediated message is delivered
**Then** only the recipient can see that guidance.

### Pass criteria

* The sender cannot view recipient guidance.
* The guidance does not reveal unnecessary private analysis.
* The guidance is clearly marked as optional support.

**Priority:** Critical

---

## AT-25 — Guidance does not manipulate

**Given** the AI provides private guidance
**When** the participant reads it
**Then** the guidance should support communication without pressuring a specific outcome.

### Pass criteria

* The AI does not tell a participant they must forgive, agree, reconcile, or continue.
* The AI does not take sides.
* The participant remains free to decide what to do.

**Priority:** Critical

---

## AT-26 — Suggest a pause when appropriate

**Given** the conversation becomes highly tense or repetitive
**When** the AI evaluates the message
**Then** it may privately recommend a pause.

### Pass criteria

* The recommendation is calm and non-judgmental.
* The system does not automatically end the conversation without a defined safety reason.
* Clear requests for space are respected.

**Priority:** Normal

---

# 8. Safety and Harmful Content

## AT-27 — Do not merely soften a credible threat

**Given** a participant sends a credible threat of violence or serious harm
**When** the AI processes it
**Then** the system does not simply rewrite and deliver it as an ordinary message.

### Pass criteria

* The content is classified as high risk.
* Delivery follows the defined safety policy.
* The system provides an appropriate safety response.
* The raw threat is not casually exposed to the recipient through ordinary mediation.

**Priority:** Critical

---

## AT-28 — Handle coercive content

**Given** a message contains coercion, intimidation, or pressure
**When** the AI mediates it
**Then** the system does not disguise the coercion as harmless communication.

### Pass criteria

* Important safety meaning is preserved.
* The recipient is not misled about the seriousness of the message.
* The AI does not normalize abusive pressure.

**Priority:** Critical

---

## AT-29 — Handle self-harm indicators

**Given** a message includes a credible indication of self-harm or immediate danger
**When** the AI processes it
**Then** the system follows the applicable safety response rather than ordinary mediation alone.

### Pass criteria

* The risk is not ignored.
* The system does not provide harmful instructions.
* The response prioritizes immediate safety while remaining calm.

**Priority:** Critical

---

# 9. Conversation Display and Privacy

## AT-30 — Recipient sees only the mediated message

**Given** Participant A sends a raw message
**When** Participant B views the conversation
**Then** Participant B sees only the mediated version.

### Pass criteria

* The raw message is absent from the recipient interface.
* Browser inspection does not expose raw message content through the recipient API response.
* The sender may view their own original message if the product design allows it.

**Priority:** Critical

---

## AT-31 — Conversation history is chronological

**Given** several messages have been exchanged
**When** either participant views the room
**Then** messages appear in the correct chronological order.

### Pass criteria

* No messages are duplicated.
* No messages appear before earlier messages.
* Sender identity is clear.
* Mediation status is accurately displayed.

**Priority:** Critical

---

## AT-32 — Unauthorized users cannot access the room

**Given** a person has no valid participant session or invitation
**When** they request conversation data
**Then** the system denies access.

### Pass criteria

* Messages are not returned.
* Participant information is not returned.
* Private guidance is not returned.
* Access control is enforced by the backend, not only the interface.

**Priority:** Critical

---

## AT-33 — One participant cannot view the other's private guidance

**Given** both participants are in the same room
**When** either participant requests guidance data
**Then** they receive only guidance addressed to them.

### Pass criteria

* Access is checked by participant identity.
* Changing a client-side identifier does not expose the other participant's guidance.

**Priority:** Critical

---

# 10. Real-Time Communication

## AT-34 — New messages appear without manual refresh

**Given** both participants are viewing the conversation
**When** one participant sends a message and mediation succeeds
**Then** the other participant receives the message without refreshing the page.

### Pass criteria

* The delivered message appears automatically.
* Messages are not duplicated.
* The user interface remains responsive.

**Priority:** Critical

---

## AT-35 — Mediation status is visible

**Given** the AI is still processing a submitted message
**When** the sender views the conversation
**Then** the interface shows that mediation is in progress.

### Pass criteria

* The sender knows the message has not yet been delivered.
* The message is not falsely marked as delivered.
* The user cannot accidentally submit the same message repeatedly without warning.

**Priority:** Normal

---

# 11. AI and System Failure

## AT-36 — AI service unavailable

**Given** the OpenAI service is unavailable or returns an error
**When** a participant submits a message
**Then** the raw message is not delivered to the recipient.

### Pass criteria

* The sender receives a clear error or retry status.
* The original message remains available for retry.
* The recipient receives nothing until mediation succeeds.
* The system never bypasses AI mediation.

**Priority:** Critical

---

## AT-37 — Invalid AI response

**Given** the AI returns missing, malformed, or invalid structured output
**When** the backend validates the response
**Then** the message is not delivered.

### Pass criteria

* Invalid output is rejected.
* The sender receives an appropriate retry status.
* No broken or incomplete message appears to the recipient.
* The failure is logged without exposing sensitive content unnecessarily.

**Priority:** Critical

---

## AT-38 — Duplicate submission protection

**Given** a participant presses Send multiple times or a network request is retried
**When** the backend receives duplicate requests
**Then** the message is processed and delivered only once.

### Pass criteria

* Duplicate mediated messages do not appear.
* A stable message identifier or idempotency mechanism is used.

**Priority:** Normal

---

# 12. Conversation Completion and Summary

## AT-39 — End the conversation

**Given** a participant chooses to end the conversation
**When** the action is confirmed
**Then** the conversation status changes from active to ended.

### Pass criteria

* New messages can no longer be submitted unless reopening is explicitly supported.
* Both participants can see that the conversation has ended.
* Existing history remains available according to the product's retention policy.

**Priority:** Critical

---

## AT-40 — Generate a neutral summary

**Given** an ended conversation contains enough messages
**When** a summary is requested or automatically generated
**Then** the AI creates a neutral summary.

### Pass criteria

* The summary identifies the main topics.
* It distinguishes agreement from disagreement.
* It does not declare a winner.
* It does not invent decisions or commitments.
* It preserves explicit boundaries and unresolved issues.

**Priority:** Critical

---

## AT-41 — Empty or very short conversation summary

**Given** a conversation contains little or no meaningful content
**When** a summary is requested
**Then** the system does not fabricate a detailed summary.

### Pass criteria

* The summary states that there was insufficient discussion.
* No invented agreement, conflict, or outcome is added.

**Priority:** Normal

---

# 13. User Experience

## AT-42 — The product does not resemble a three-person group chat

**Given** a participant uses the conversation screen
**When** they exchange mediated messages
**Then** the interface should feel like communication between two people.

### Pass criteria

* The AI is not displayed as a normal third speaker.
* AI guidance is visually separate from participant messages.
* The conversation remains centered on the two participants.

**Priority:** Critical

---

## AT-43 — AI involvement is understandable

**Given** a new participant enters a room
**When** they view the interface
**Then** they understand that messages are mediated and may be translated before delivery.

### Pass criteria

* The role of AI is clearly explained.
* The participant is not misled into believing raw messages are delivered unchanged.
* The explanation is concise and understandable.

**Priority:** Critical

---

## AT-44 — Interface works on desktop and mobile browsers

**Given** a participant opens the application on a supported browser
**When** they create, join, or use a conversation
**Then** the core interface remains usable.

### Pass criteria

* Message input is accessible.
* Messages are readable.
* Buttons are not cut off.
* Invitation links can be copied.
* No horizontal scrolling is required for normal use.

**Priority:** Normal

---

# 14. Final Definition of Done

The MVP is considered complete when:

* all **Critical** acceptance tests pass,
* no critical security or privacy issue remains open,
* mediation works in both same-language and multilingual conversations,
* raw messages are never exposed to the recipient,
* essential meaning and boundaries are preserved,
* AI failures never result in unmediated delivery,
* two participants can complete the full conversation flow,
* the final experience clearly demonstrates the purpose of 2talk.

The MVP is not considered complete merely because the screens exist.

The complete communication flow must work from conversation creation through mediated exchange and final summary.
