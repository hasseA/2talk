# 03_MVP_SPEC.md

# Minimum Viable Product (MVP) Specification

## 1. Objective

The goal of the MVP is to demonstrate that AI-mediated communication between two people is practical and useful.

This version is intentionally small.

It should implement one complete communication flow from beginning to end rather than many unfinished features.

---

# 2. Core User Journey

The entire application should support the following workflow:

1. A participant creates a private conversation.
2. A secure invitation link is generated.
3. A second participant joins the conversation.
4. Each participant selects their preferred language.
5. Both participants exchange mediated messages.
6. The AI interprets, translates, and mediates every message.
7. The conversation ends with an optional AI-generated summary.

If this workflow works well, the MVP is considered successful.

---

# 3. Required Screens

## Landing Page

Purpose:

Explain what 2talk is.

Contains:

* product description
* how AI mediation works
* Create Conversation button

---

## Create Conversation

Fields:

* Conversation title (optional)
* Your display name
* Preferred language
* Optional conversation description

Actions:

* Create Conversation
* Generate invitation link

---

## Join Conversation

Fields:

* Display name
* Preferred language

Actions:

* Join Conversation

---

## Conversation Screen

Displays:

* Mediated conversation
* Message input
* Send button
* Private AI guidance (only visible to the current participant)
* Conversation status

---

## Conversation Summary

Displayed when the conversation ends.

Contains:

* neutral summary
* main discussion topics
* points of agreement
* remaining disagreements
* conversation duration

---

# 4. Required Features

The MVP must include:

✓ Private conversation rooms

✓ Invitation link

✓ Two participants only

✓ AI mediation of every message

✓ Automatic language translation

✓ Conversation history

✓ Private AI guidance

✓ AI-generated conversation summary

---

# 5. Language Support

Each participant independently chooses their preferred language.

Example:

Participant A writes in Swedish.

Participant B writes in English.

The AI should:

* understand the original message,
* mediate the meaning,
* deliver the message in the recipient's language.

Neither participant should need to manually translate messages.

---

# 6. Conversation Rules

Every message must pass through the AI before delivery.

The recipient never receives the sender's raw message directly.

The AI always delivers the mediated version.

---

# 7. Explicitly Out of Scope

The MVP will NOT include:

* user accounts
* public profiles
* friend lists
* public discussions
* discussion forums
* expert panels
* audience participation
* voice chat
* video chat
* file sharing
* reactions or emojis
* payments
* subscriptions
* notifications
* multiple AI providers
* local language models
* mobile applications

These features may be added in future versions.

---

# 8. Success Criteria

The MVP is successful if two people can:

* create a conversation,
* join using an invitation link,
* communicate in different languages,
* receive mediated messages,
* experience fewer misunderstandings,
* finish the conversation with a useful AI summary.

The success of the MVP is measured by the quality of communication rather than the number of features.
