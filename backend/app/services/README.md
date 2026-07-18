# Service-layer conventions

Services own business rules, authorization decisions, cross-repository orchestration, and transaction boundaries. Every mutating public method uses `async with session.begin()`: normal completion commits once, while any exception rolls the entire operation back.

Repositories remain persistence-only and never commit. Join operations serialize on the conversation row before invitation state is reloaded and participant capacity is checked. Message delivery updates the message, delivery row, and participant-specific guidance inside one transaction.

The AI mediation orchestrator is the only service allowed to call `AIProvider`. It
uses three short phases so external provider latency never holds a PostgreSQL
transaction or row lock open:

```text
Message
  -> claim transaction (lock, validate, create attempt, build safe context)
  -> release database transaction
  -> AI provider call
  -> finalization transaction (lock, verify current attempt, write outcome)
  -> final state
```

The message row serializes claims. A current `started` attempt causes duplicate
workers to return `already_processing`, while terminal messages return an
idempotent `already_finalized` outcome. The present schema has no claim lease or
expiry timestamp: if a process dies after claiming and before finalization, the
message remains processing until an operational recovery mechanism is added in a
later execution milestone.

Message creation and retry retain their documented immediate `processing`
responses while atomically enqueueing the durable PostgreSQL job. The separate
AI worker invokes orchestration; FastAPI does not run an in-process worker.
