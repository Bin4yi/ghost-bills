"""Lock 1: Penny's delegated, read-only token, and the API's token checks."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend import seed_demo
from backend.agent import graph
from backend.app import app
from backend.auth import web

from . import fake_auth0 as fa


@pytest.fixture
def rt():
    """Agents set up against the fake tenant (no network)."""
    old = app.state.agents
    app.state.agents = runtime = fa.fake_runtime()
    yield runtime
    app.state.agents = old


@pytest.fixture
def logged_in(monkeypatch, rt):
    async def user(request, response):
        return {"sub": fa.USER, "name": "Test Person"}

    async def token(request, response):
        return fa.mint(aud=fa.SETTINGS.login_audience, scope="openid profile email")

    monkeypatch.setattr(web, "current_user", user)
    monkeypatch.setattr(web, "user_access_token", token)
    return rt


@pytest.fixture
def demo(tmp_path):
    seed_demo.seed(tmp_path / "demo.csv", reset=False)


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- the API's checks -------------------------------------------------------------

def test_good_penny_token_passes(rt, demo) -> None:
    r = TestClient(app).get("/api/ghosts", headers=bearer(fa.penny_token()))
    assert r.status_code == 200 and len(r.json()) == 5


@pytest.mark.parametrize("token, status, words", [
    (fa.penny_token(exp_in=-30), 401, "expired"),
    (fa.penny_token(aud=fa.SETTINGS.courier_audience), 403, "different API"),
    (fa.penny_token(scope="openid"), 403, "read:ghosts"),
    (fa.penny_token(wrong_key=True), 401, "not valid"),
    (fa.penny_token(iss="https://evil.example/"), 401, "not"),
    ("not-a-jwt", 401, "not valid"),
])
def test_bad_tokens_are_refused(rt, demo, token, status, words) -> None:
    r = TestClient(app).get("/api/ghosts", headers=bearer(token))
    assert r.status_code == status, r.text
    assert words in r.json()["detail"]


def test_ask_and_ledger_need_read_scope(rt, demo) -> None:
    no_scope = bearer(fa.penny_token(scope="openid"))
    assert TestClient(app).get("/api/agent/ledger", headers=no_scope).status_code == 403
    assert TestClient(app).post("/api/ask", json={"question": "hi"}, headers=no_scope).status_code == 403


def test_remote_caller_without_token_is_refused(rt, demo) -> None:
    remote = TestClient(app, client=("203.0.113.9", 4000))
    r = remote.get("/api/ghosts")
    assert r.status_code == 401 and "read:ghosts" in r.json()["detail"]


def test_local_ui_needs_no_token(demo) -> None:
    """Logged out / offline: the page on this laptop works exactly as before."""
    client = TestClient(app)
    assert client.get("/api/ghosts").status_code == 200
    assert client.post("/api/ghosts/sleepy:cloudcrate/status", json={"status": "kept"}).status_code == 200


def test_agents_cannot_change_status(rt, demo) -> None:
    r = TestClient(app).post("/api/ghosts/sleepy:cloudcrate/status", json={"status": "cancelled"},
                             headers=bearer(fa.penny_token()))
    assert r.status_code == 403


# --- token exchange 1: user -> Penny ------------------------------------------------

class Script:
    def __init__(self, routes, answers):
        self.routes, self.answers = list(routes), list(answers)

    def __call__(self, system, user, schema):
        if "action" in schema["properties"]:
            return self.routes.pop(0) if self.routes else {"action": "answer"}
        return {"text": self.answers.pop(0)}


def test_penny_gets_a_read_only_delegated_token(logged_in, demo, monkeypatch) -> None:
    script = Script([{"action": "tool", "tool": "list_ghosts", "args": {}}],
                    ["Your biggest ghost is Pixelpal Pro."])
    monkeypatch.setattr(graph.ask, "__defaults__", (script, None))
    r = TestClient(app).post("/api/ask", json={"question": "Which ghost first?"})
    assert r.status_code == 200 and "Pixelpal" in r.json()["text"]

    exchange = logged_in.gateway.exchanges[0]
    assert exchange == {"client_id": fa.PENNY, "audience": fa.SETTINGS.ledger_audience,
                        "scope": "read:ghosts"}
    held = logged_in.tokens.penny[fa.USER]
    assert held.claims["sub"] == fa.USER and held.claims["act"]["sub"] == fa.PENNY
    assert held.claims["scope"] == "read:ghosts"

    # Cached: a second question doesn't exchange again.
    monkeypatch.setattr(graph.ask, "__defaults__", (Script([], ["Hi."]), None))
    TestClient(app).post("/api/ask", json={"question": "hi"})
    assert len(logged_in.gateway.exchanges) == 1


def test_penny_token_is_refreshed_before_expiry(logged_in, demo, monkeypatch) -> None:
    monkeypatch.setattr(graph.ask, "__defaults__", (Script([], ["a", "b"]), None))
    TestClient(app).post("/api/ask", json={"question": "hi"})
    logged_in.tokens.penny[fa.USER].expires_at = 0  # about to expire
    TestClient(app).post("/api/ask", json={"question": "hi"})
    assert len(logged_in.gateway.exchanges) == 2


def test_inspector_shows_claims_never_tokens(logged_in, demo, monkeypatch) -> None:
    monkeypatch.setattr(graph.ask, "__defaults__", (Script([], ["ok"]), None))
    TestClient(app).post("/api/ask", json={"question": "hi"})
    r = TestClient(app).get("/api/agents/tokens")
    body = r.json()
    assert body["penny"]["sub"] == fa.USER and body["penny"]["act"]["sub"] == fa.PENNY
    assert body["penny"]["scope"] == "read:ghosts" and body["penny"]["exp"] > 0
    assert body["courier"] is None
    assert "eyJ" not in r.text


def test_stop_all_agents_blocks_the_next_exchange(logged_in, demo, monkeypatch) -> None:
    monkeypatch.setattr(graph.ask, "__defaults__", (Script([], ["ok"]), None))
    client = TestClient(app)
    client.post("/api/ask", json={"question": "hi"})
    assert client.post("/api/agents/stop").json() == {"stopped": True}
    assert client.get("/api/agents/tokens").json() == {"stopped": True, "penny": None, "courier": None}
    r = client.post("/api/ask", json={"question": "hi"})
    assert "stopped" in r.json()["text"]
    assert len(logged_in.gateway.exchanges) == 1  # no new exchange
    logged_in.tokens.resume()  # what a fresh login does
    monkeypatch.setattr(graph.ask, "__defaults__", (Script([], ["back"]), None))
    assert client.post("/api/ask", json={"question": "hi"}).json()["text"] == "back"
    assert len(logged_in.gateway.exchanges) == 2


def test_agents_cannot_stop_or_inspect(rt) -> None:
    client = TestClient(app)
    assert client.post("/api/agents/stop", headers=bearer(fa.penny_token())).status_code == 403
    assert client.get("/api/agents/tokens", headers=bearer(fa.penny_token())).status_code == 403
