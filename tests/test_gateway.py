"""The real Auth0 and Gmail call paths, with the network replaced underneath them."""

from __future__ import annotations

import asyncio
import base64
import json
from email import message_from_bytes

import pytest
from auth0.authentication.back_channel_login import BackChannelLogin
from auth0.authentication.get_token import GetToken
from auth0.exceptions import Auth0Error

from backend.agents import gmail
from backend.agents.gateway import Auth0Gateway

from . import fake_auth0 as fa


def test_start_approval_sends_the_right_ciba_request(monkeypatch) -> None:
    seen = {}

    def fake(self, **kwargs):
        seen.update(kwargs, client_id=self.client_id)
        return {"auth_req_id": "abc", "expires_in": 120, "interval": 5}

    monkeypatch.setattr(BackChannelLogin, "back_channel_login", fake)
    out = Auth0Gateway(fa.SETTINGS).start_approval("Send cancel email to x.example about X",
                                                  fa.USER, fa.SETTINGS.courier_audience,
                                                  "openid send:cancel_email", 120)
    assert out["auth_req_id"] == "abc"
    assert json.loads(seen["login_hint"]) == {"format": "iss_sub", "iss": fa.ISSUER, "sub": fa.USER}
    assert seen["requested_expiry"] == 120 and seen["audience"] == fa.SETTINGS.courier_audience
    assert seen["scope"] == "openid send:cancel_email"
    assert seen["client_id"] == fa.COURIER  # CIBA falls back to Courier's client


@pytest.mark.parametrize("code, state", [
    ("authorization_pending", "pending"), ("slow_down", "slow_down"),
    ("access_denied", "denied"), ("expired_token", "expired"), ("something_else", "error"),
])
def test_poll_maps_ciba_errors(monkeypatch, code, state) -> None:
    def fake(self, auth_req_id, grant_type="urn:openid:params:grant-type:ciba"):
        raise Auth0Error(400, code, "nope")

    monkeypatch.setattr(GetToken, "backchannel_login", fake)
    assert Auth0Gateway(fa.SETTINGS).poll_approval("abc")["state"] == state


def test_poll_approved(monkeypatch) -> None:
    monkeypatch.setattr(GetToken, "backchannel_login",
                        lambda self, auth_req_id, grant_type=None: {"access_token": "t"})
    assert Auth0Gateway(fa.SETTINGS).poll_approval("abc") == {"state": "approved", "access_token": "t"}


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
