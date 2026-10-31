"""The real Auth0 and Gmail call paths, with the network replaced underneath them."""

from __future__ import annotations

import asyncio
import base64
from email import message_from_bytes

import pytest
from auth0.authentication.get_token import GetToken
from auth0.exceptions import Auth0Error

from backend.agents import gmail
from backend.agents.gateway import Auth0Gateway

from . import fake_auth0 as fa


def test_exchange_code_sends_the_secret_and_pkce_verifier(monkeypatch) -> None:
    seen = {}

    def fake(self, url, data, headers=None):
        seen.update(data, url=url, sdk_client_id=self.client_id, secret=self.client_secret)
        return {"id_token": "x"}

    monkeypatch.setattr(GetToken, "authenticated_post", fake)
    out = asyncio.run(Auth0Gateway(fa.SETTINGS).exchange_code(
        "the-code", "the-verifier", fa.SETTINGS.step_up_redirect))
    assert out == {"id_token": "x"}
    assert seen["url"] == f"https://{fa.DOMAIN}/oauth/token"
    assert seen["grant_type"] == "authorization_code" and seen["code"] == "the-code"
    assert seen["code_verifier"] == "the-verifier"
    assert seen["redirect_uri"] == fa.SETTINGS.step_up_redirect
    assert seen["client_id"] == seen["sdk_client_id"] == fa.SETTINGS.client_id
    assert seen["secret"] == "web-secret"  # authenticated_post adds the Web app's secret


def test_exchange_code_refusal_is_plain(monkeypatch) -> None:
    from backend.auth.tokens import TokenError

    def fake(self, url, data, headers=None):
        raise Auth0Error(403, "invalid_grant", "nope")

    monkeypatch.setattr(GetToken, "authenticated_post", fake)
    with pytest.raises(TokenError) as err:
        asyncio.run(Auth0Gateway(fa.SETTINGS).exchange_code("c", "v", "r"))
    assert err.value.status == 401


def test_on_behalf_of_uses_the_sdk(monkeypatch) -> None:
    from auth0_api_python import ApiClient
    seen = {}

    async def fake(self, access_token, audience, scope=None):
        seen.update(client_id=self.options.client_id, audience=audience, scope=scope,
                    subject_audience=self.options.audience)
        return {"access_token": "x", "expires_in": 300, "expires_at": 1}

    monkeypatch.setattr(ApiClient, "get_token_on_behalf_of", fake)
    asyncio.run(Auth0Gateway(fa.SETTINGS).on_behalf_of(
        fa.COURIER, "s", "subject", fa.SETTINGS.ledger_audience, fa.SETTINGS.courier_audience,
        "send:cancel_email"))
    assert seen == {"client_id": fa.COURIER, "audience": fa.SETTINGS.courier_audience,
                    "scope": "send:cancel_email", "subject_audience": fa.SETTINGS.ledger_audience}


def test_gmail_send_builds_one_message(monkeypatch) -> None:
    seen = {}

    class Resp:
        status_code = 200

        def json(self):
            return {"id": "msg-1"}

    def fake_post(url, headers, json, timeout):
        seen.update(url=url, auth=headers["Authorization"], raw=json["raw"])
        return Resp()

    monkeypatch.setattr(gmail.httpx, "post", fake_post)
    msg_id = gmail.GmailSender().send("google-token", "support@x.example", "Please cancel my X",
                                      "Hello,\n\nPlease cancel my X subscription.")
    assert msg_id == "msg-1"
    assert seen["url"].endswith("/gmail/v1/users/me/messages/send")
    assert seen["auth"] == "Bearer google-token"
    parsed = message_from_bytes(base64.urlsafe_b64decode(seen["raw"]))
    assert parsed["To"] == "support@x.example" and parsed["Subject"] == "Please cancel my X"


def test_gmail_refusal_raises_without_the_token(monkeypatch) -> None:
    class Resp:
        status_code = 403

    monkeypatch.setattr(gmail.httpx, "post", lambda *a, **k: Resp())
    with pytest.raises(RuntimeError) as err:
        gmail.GmailSender().send("secret-google-token", "a@b.example", "s", "b")
    assert "secret-google-token" not in str(err.value)
