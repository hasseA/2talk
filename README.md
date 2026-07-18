# 2talk

Production-oriented project skeleton for the 2talk MVP.

## Development with Docker

1. Optionally set `OPENAI_API_KEY` in a root `.env` file.
2. Run `docker compose up --build`.
3. Open the frontend at <http://localhost:5173>.
4. Check the backend at <http://localhost:8000/health>.

The repository intentionally contains only application startup scaffolding. Feature logic, database models, migrations, authentication, and integrations have not been implemented.

## Project areas

- `backend/`: FastAPI, Alembic, pytest, Ruff, and Black configuration.
- `frontend/`: React, TypeScript, Vite, and Playwright configuration.
- `docker/`: Container definitions for each service.
- `scripts/`: Placeholder for development and operational tooling.
- `docs/`: Existing project documentation.
