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

## Project areas

- `backend/`: FastAPI, Alembic, pytest, Ruff, and Black configuration.
- `frontend/`: React, TypeScript, Vite, and Playwright configuration.
- `docker/`: Container definitions for each service.
- `scripts/`: Placeholder for development and operational tooling.
- `docs/`: Existing project documentation.
