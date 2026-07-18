# Durable AI mediation worker

The HTTP process only commits durable work:

```text
HTTP transaction
  -> message + durable job committed

Worker claim transaction
  -> SELECT FOR UPDATE SKIP LOCKED
  -> lease job
  -> commit

No database transaction
  -> orchestration
  -> AI provider

Worker finalization transaction
  -> complete, cancel, or dead-letter job
```

Run the dedicated process with:

```text
python -m app.workers.ai_mediation_worker
```

The worker is never started by FastAPI. A lease is configured to exceed the
provider timeout plus finalization margin, so this milestone does not use a
heartbeat. Every AI attempt records its execution lease token. Orchestration
checks that token and its unexpired job lease before both claim and finalization,
preventing an expired or superseded worker from changing message state.

Expired leases with no started attempt are queued immediately. A latest started
attempt is rejected as `WORKER_LEASE_EXPIRED` only after the configured stale
threshold, while the message is still processing, no delivery exists, and its
lease token still matches the expired job. Recovery then requeues the same job;
the next execution creates the next ordered AI attempt without incrementing the
product-level `retry_count`.

AI provider failures use explicit sender-controlled retry: orchestration marks
the message failed and the worker marks the job dead. No automatic provider
retry loop is performed. The documented retry endpoint atomically increments
the message retry count and reactivates the same durable job row.
