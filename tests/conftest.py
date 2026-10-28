from __future__ import annotations

from pathlib import Path

import pytest

from backend import settings

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Every test gets its own empty SQLite file and the fixed demo 'today'."""
    path = tmp_path / "test.db"
    monkeypatch.setattr(settings, "DB_PATH", path)
    monkeypatch.setenv("DEMO_TODAY", "2026-10-27")
    return path
