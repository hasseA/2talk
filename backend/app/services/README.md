# Service-layer conventions

Services own business rules, authorization decisions, cross-repository orchestration, and transaction boundaries. Every mutating public method uses `async with session.begin()`: normal completion commits once, while any exception rolls the entire operation back.

Repositories remain persistence-only and never commit. Join operations serialize on the conversation row before invitation state is reloaded and participant capacity is checked. Message delivery updates the message, delivery row, and participant-specific guidance inside one transaction.

This layer contains no HTTP, authentication middleware, AI calls, or realtime behavior.
