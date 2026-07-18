# 2talk backend

FastAPI API, PostgreSQL persistence, Alembic migrations, and the durable AI
mediation worker for the 2talk hackathon release.

## Local development

1. Create and activate a Python 3.12 virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and supply local values.
4. Apply migrations with `alembic upgrade head`.
5. Start the API with `uvicorn app.main:app --reload`.
6. In a separate terminal, start mediation with
   `python -m app.workers.ai_mediation_worker`.

For tests, set `TEST_DATABASE_URL` to a dedicated PostgreSQL database whose
name ends in `_test`; tests reject non-test database names. Run:

```powershell
$env:TEST_DATABASE_URL='postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/twotalk_test'
.\.venv\Scripts\python -m pytest -q tests -p no:cacheprovider
.\.venv\Scripts\ruff check --no-cache app tests
.\.venv\Scripts\black --check --fast --workers 1 app tests
.\.venv\Scripts\python -m pip check
```

The repository root README documents the recommended Docker Compose workflow.
