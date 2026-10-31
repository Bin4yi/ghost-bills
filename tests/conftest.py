from __future__ import annotations

import os
from pathlib import Path

import pytest

# Tests never read a developer's real .env and never talk to a real Auth0 tenant.
os.environ["GHOST_NO_DOTENV"] = "1"
for _key in ("AUTH0_DOMAIN", "AUTH0_CLIENT_ID", "AUTH0_CLIENT_SECRET", "SESSION_SECRET"):
    os.environ.pop(_key, None)

from backend import settings  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Every test gets its own empty SQLite file and the fixed demo 'today'."""
    path = tmp_path / "test.db"
    monkeypatch.setattr(settings, "DB_PATH", path)
    monkeypatch.setenv("DEMO_TODAY", "2026-10-27")
    return path
