# Repository conventions

Repositories receive an `AsyncSession` and perform database access only. They may add entities, execute explicit queries, flush pending changes, and refresh state. They never call `commit()` or own multi-repository transaction workflows; the future service layer controls atomic boundaries and product policy.

Privacy-sensitive reads use explicit projections. In particular, recipient message queries return `IncomingMessageProjection`, which cannot contain an original message, and participant guidance queries always require and filter by a participant ID.
