"""A fake Auth0 tenant for tests: real RS256 keys and JWKS, no network.

Tokens are checked by the real auth0-api-python verifier (through its
`custom_fetch` hook). Exchanges, Token Vault, the step-up code exchange and Gmail are fakes that
record what they were asked to do.
"""

from __future__ import annotations

import json
import time
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from backend.agents.runtime import AgentRuntime
from backend.agents.vault import AgentTokens
from backend.auth.config import AuthSettings
from backend.auth.tokens import Verifier

DOMAIN = "ghost-test.example.auth0.com"
ISSUER = f"https://{DOMAIN}/"
PENNY = "penny-client-id"
COURIER = "courier-client-id"
USER = "google-oauth2|1234567890"

SETTINGS = AuthSettings(
    domain=DOMAIN, client_id="web-client", client_secret="web-secret", session_secret="s" * 48,
    login_audience="https://ghost-bills.local/login",
    ledger_audience="https://ghost-bills.local/ledger",
    courier_audience="https://ghost-bills.local/courier",
    penny_client_id=PENNY, penny_client_secret="penny-secret",
    courier_client_id=COURIER, courier_client_secret="courier-secret")

_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_JWK = json.loads(RSAAlgorithm.to_jwk(_KEY.public_key())) | {"kid": "test-key", "use": "sig", "alg": "RS256"}


async def custom_fetch(url: str) -> dict[str, Any]:
    if url.endswith("/.well-known/openid-configuration"):
        return {"issuer": ISSUER, "jwks_uri": f"{ISSUER}.well-known/jwks.json",
                "token_endpoint": f"{ISSUER}oauth/token"}
    if url.endswith("jwks.json"):
        return {"keys": [_JWK]}
    raise AssertionError(f"unexpected fetch {url}")


def mint(sub: str = USER, aud: str = SETTINGS.ledger_audience, scope: str = "read:ghosts",
         act: dict | None = None, exp_in: int = 300, iss: str = ISSUER, wrong_key: bool = False,
         azp: str | None = None) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {"iss": iss, "sub": sub, "aud": aud, "iat": now, "nbf": now - 1,
                              "exp": now + exp_in, "scope": scope}
    if act:
        claims["act"] = act
    if azp:
        claims["azp"] = azp
    key = _OTHER_KEY if wrong_key else _KEY
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test-key"})


def penny_token(**kw: Any) -> str:
    return mint(act={"sub": PENNY}, azp=PENNY, **kw)


def id_token(nonce: str, sub: str = USER, auth_age: int = 5,
             aud: str = SETTINGS.client_id, wrong_key: bool = False) -> str:
    """The ID token from the fresh confirmation login on the Web app."""
    now = int(time.time())
    claims = {"iss": ISSUER, "sub": sub, "aud": aud, "iat": now, "exp": now + 600,
              "nonce": nonce, "auth_time": now - auth_age, "amr": ["pwd"]}
    key = _OTHER_KEY if wrong_key else _KEY
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test-key"})


class FakeGateway:
    def __init__(self, nest_act: bool = True) -> None:
        self.nest_act = nest_act
        self.exchanges: list[dict[str, Any]] = []
        self.vault_calls: list[dict[str, Any]] = []
        self.code_exchanges: list[dict[str, Any]] = []
        self.next_id_token: str | None = None

    async def on_behalf_of(self, client_id, client_secret, subject_token, subject_audience,
                           audience, scope):
        prior = jwt.decode(subject_token, options={"verify_signature": False})
        act: dict[str, Any] = {"sub": client_id}
        if self.nest_act and prior.get("act"):
            act["act"] = prior["act"]
        self.exchanges.append({"client_id": client_id, "audience": audience, "scope": scope})
        expires = 300
        token = mint(sub=prior["sub"], aud=audience, scope=scope, act=act, exp_in=expires,
                     azp=client_id)
        return {"access_token": token, "expires_in": expires, "expires_at": int(time.time()) + expires,
                "scope": scope, "token_type": "Bearer"}

    async def token_vault(self, client_id, client_secret, subject_token, subject_audience, connection):
        self.vault_calls.append({"client_id": client_id, "connection": connection})
        return {"access_token": "fake-google-access-token-0123456789",
                "expires_in": 3599, "scope": "https://www.googleapis.com/auth/gmail.send"}

    async def exchange_code(self, code, code_verifier, redirect_uri):
        self.code_exchanges.append({"code": code, "redirect_uri": redirect_uri})
        if self.next_id_token is None:
            from backend.auth.tokens import TokenError
            raise TokenError(401, "Auth0 did not accept the approval.")
        return {"id_token": self.next_id_token, "access_token": "unused"}


class FakeGmail:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    def send(self, google_token, to_address, subject, body):
        self.sent.append({"to": to_address, "subject": subject, "body": body})
        return f"gmail-msg-{len(self.sent)}"


def fake_runtime(nest_act: bool = True) -> AgentRuntime:
    return AgentRuntime(settings=SETTINGS, verifier=Verifier(SETTINGS, custom_fetch=custom_fetch),
                        gateway=FakeGateway(nest_act=nest_act), tokens=AgentTokens(),
                        gmail=FakeGmail())
