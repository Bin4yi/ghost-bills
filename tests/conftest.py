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


# --- fake Auth0 tenant (no network) ---------------------------------------------------

@pytest.fixture
def rt():
    """Agents set up against the fake tenant."""
    from backend.app import app

    from . import fake_auth0 as fa
    old = app.state.agents
    app.state.agents = runtime = fa.fake_runtime()
    yield runtime
    app.state.agents = old


@pytest.fixture
def logged_in(monkeypatch, rt):
    """A logged-in user, without a real Auth0 session cookie."""
    from backend.auth import web

    from . import fake_auth0 as fa

    async def user(request, response):
        return {"sub": fa.USER, "name": "Test Person"}

    async def token(request, response):
        return fa.mint(aud=fa.SETTINGS.login_audience, scope="openid profile email")

    monkeypatch.setattr(web, "current_user", user)
    monkeypatch.setattr(web, "user_access_token", token)
    return rt


@pytest.fixture
def demo(tmp_path):
    from backend import seed_demo
    seed_demo.seed(tmp_path / "demo.csv", reset=False)
