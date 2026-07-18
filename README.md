# 2talk

2talk is a two-participant conversation MVP with AI-mediated messages, a
FastAPI backend, a React frontend, and PostgreSQL persistence.

## Local/demo development with Docker

1. Copy `.env.example` to `.env`.
2. Replace `OPENAI_API_KEY` with a valid key. The AI worker will not start
   without it.
3. Change the session, invitation, and database secret placeholders.
4. Run `docker compose up --build`.
5. Open the frontend at <http://localhost:5173>.
6. Check the backend at <http://localhost:8000/api/v1/health>.

The one-shot `migrate` service waits for PostgreSQL, applies `alembic upgrade
head`, and must complete successfully before the backend and AI worker start.

To avoid host-port conflicts, override `POSTGRES_PORT`, `BACKEND_PORT`, or
`FRONTEND_PORT` in the root `.env`. For example, setting
`FRONTEND_PORT=55173` exposes the frontend at <http://localhost:55173> while
the internal container port remains unchanged.

This Compose stack is intended for local development and demonstrations. It
uses development servers and is not a hardened production deployment.

## Hackathon release scope

The current submission implements the two-participant create, invite, join,
message-mediation, private-guidance, retry, and end-conversation flow. The UI
uses short polling for near-real-time updates and supports English (`en`),
Swedish (`sv`), and Persian (`fa`).

The files in `docs/` describe the broader MVP product target. In particular,
AI-generated conversation summaries are specified there but are not implemented
in this hackathon release. Ending a conversation makes it read-only; it does not
generate or display a summary. This local/demo stack does not provide SSE,
WebSockets, TLS termination, or production deployment hardening.

## Verification commands

Backend checks require a separate PostgreSQL database whose name ends in
`_test`:

```powershell
cd backend
$env:TEST_DATABASE_URL='postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/twotalk_test'
.\.venv\Scripts\python -m pytest -q tests -p no:cacheprovider
.\.venv\Scripts\ruff check --no-cache app tests
.\.venv\Scripts\black --check --fast --workers 1 app tests
.\.venv\Scripts\python -m pip check
```

Frontend checks require dependencies and Playwright's Chromium browser:

```powershell
cd frontend
npm install
npx playwright install chromium
npm run typecheck
npm test
npm run build
npm audit
```

## Project areas

- `backend/`: FastAPI, Alembic, pytest, Ruff, and Black configuration.
- `frontend/`: React, TypeScript, Vite, and Playwright configuration.
- `docker/`: Container definitions for each service.
- `scripts/`: Placeholder for development and operational tooling.
- `docs/`: Existing project documentation.
