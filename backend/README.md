# 2talk backend

Minimal FastAPI development skeleton.

## Local development

1. Create and activate a Python 3.12 virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and supply local values.
4. Start the API with `uvicorn app.main:app --reload`.

Run quality checks with `ruff check .`, `black --check .`, and `pytest`.
