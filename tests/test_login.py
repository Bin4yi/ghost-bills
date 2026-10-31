from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient

from backend.app import app
from backend.auth import web
from backend.auth.config import AuthSettings, load_dotenv

FAKE = AuthSettings(domain="ghost-test.example.auth0.com", client_id="web-client",
                    client_secret="web-secret", session_secret="s" * 48,
                    login_audience="https://ghost-bills.local/login")


def test_local_mode_has_no_login() -> None:
    client = TestClient(app)
    assert client.get("/api/me").json() == {"auth_enabled": False, "logged_in": False}
    assert client.get("/auth/login", follow_redirects=False).status_code == 404
    # Everything else still works without any login.
    assert client.get("/api/health").json()["ok"] is True


def test_login_routes_mount_when_configured() -> None:
    test_app = FastAPI()
    web.install(test_app, FAKE)

    @test_app.get("/me")
    async def me(request: Request, response: Response) -> dict:
        return {"user": await web.current_user(request, response)}

    from auth0_fastapi.server.routes import router
    paths = {getattr(r, "path", None) for r in router.routes}
    assert {"/auth/login", "/auth/callback", "/auth/logout", "/auth/connect"} <= paths
    assert test_app.state.config.mount_connected_account_routes is True
    assert "offline_access" in test_app.state.config.authorization_params["scope"]
    url = web.connect_gmail_url(FAKE)
    assert url.startswith("/auth/connect?connection=google-oauth2")
    assert "gmail.send" in url and "returnTo=%2F" in url
    assert test_app.state.auth_client is not None
    # No session cookie: logged out, no error and no network call.
    assert TestClient(test_app).get("/me").json() == {"user": None}


def test_settings_flags() -> None:
    assert not AuthSettings().enabled
    assert FAKE.enabled and not FAKE.agents_ready
    ready = AuthSettings(**{**FAKE.__dict__, "ledger_audience": "l", "courier_audience": "c",
                            "penny_client_id": "p", "penny_client_secret": "ps",
                            "courier_client_id": "c", "courier_client_secret": "cs"})
    assert ready.agents_ready
    assert ready.step_up_redirect == "http://localhost:5173/auth/step-up/callback"


def test_dotenv_reader(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("GHOST_NO_DOTENV", raising=False)
    monkeypatch.delenv("GB_TEST_A", raising=False)
    monkeypatch.setenv("GB_TEST_B", "kept")
    env = tmp_path / ".env"
    env.write_text("# comment\nGB_TEST_A=hello   # trailing note\nGB_TEST_B=overwritten\n")
    load_dotenv(env)
    import os
    assert os.environ["GB_TEST_A"] == "hello"
    assert os.environ["GB_TEST_B"] == "kept"  # real env wins


def test_login_id_token_tolerates_a_slow_laptop_clock() -> None:
    """A laptop clock a few seconds behind Auth0 must not break login."""
    import asyncio
    import json
    import time

    import jwt
    import pytest
    from cryptography.hazmat.primitives.asymmetric import rsa
    from jwt.algorithms import RSAAlgorithm

    test_app = FastAPI()
    web.install(test_app, FAKE)
    verify = test_app.state.auth_client.client._verify_and_decode_jwt
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(RSAAlgorithm.to_jwk(key.public_key())) | {"kid": "k"}

    def token(iat_ahead: int) -> str:
        now = int(time.time())
        return jwt.encode({"sub": "u", "aud": "web-client", "iat": now + iat_ahead,
                           "exp": now + 600}, key, algorithm="RS256", headers={"kid": "k"})

    claims = asyncio.run(verify(token(3), {"keys": [jwk]}, audience="web-client"))
    assert claims["sub"] == "u"  # 3 s "in the future" is fine
    with pytest.raises(jwt.ImmatureSignatureError):
        asyncio.run(verify(token(300), {"keys": [jwk]}, audience="web-client"))
    with pytest.raises(jwt.InvalidAudienceError):
        asyncio.run(verify(token(0), {"keys": [jwk]}, audience="other-client"))
