"""Architectural boundaries for the AI provider package."""

from pathlib import Path

import app.ai


def test_ai_package_has_no_database_or_http_behavior() -> None:
    package_path = Path(app.ai.__file__).resolve().parent
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in package_path.rglob("*.py")
    ).lower()

    assert "sqlalchemy" not in source
    assert "fastapi" not in source
    assert ".commit(" not in source
    assert "requests." not in source
