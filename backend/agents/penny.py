"""Penny's delegated identity (Lock 1): a short, read-only token.

Token exchange 1 (On-Behalf-Of): the user's access token goes in as
`subject_token`, Penny's own client authenticates, and Auth0 returns a token
with sub = user, act = Penny, scope = read:ghosts, aud = the Ledger API.
It lives in server memory only and is re-exchanged shortly before it expires.
"""

from __future__ import annotations

from typing import Any

import httpx
from auth0_api_python import get_current_actor
from fastapi import FastAPI

from backend.agents.ledger import context_from
from backend.agents.runtime import AgentRuntime
from backend.agents.vault import Held
from backend.auth.tokens import TokenError

PENNY_SCOPE = "read:ghosts"


async def penny_token(rt: AgentRuntime, user_sub: str, user_token: str | None) -> Held:
    """Penny's current token for this user, exchanging a new one when needed."""
    rt.tokens.check_running()
    held = rt.tokens.penny.get(user_sub)
    if held and held.fresh():
        return held
    if not user_token:
        raise TokenError(401, "Log in again so Penny can get a fresh token.")
    s = rt.settings
    result = await rt.gateway.on_behalf_of(
        s.penny_client_id, s.penny_client_secret, user_token,
        subject_audience=s.login_audience, audience=s.ledger_audience, scope=PENNY_SCOPE)
    claims = await rt.verifier.verify(result["access_token"], s.ledger_audience, PENNY_SCOPE)
    check_penny_claims(claims, user_sub, s.penny_client_id)
    held = Held(result["access_token"], claims, float(result.get("expires_at") or claims["exp"]))
    rt.tokens.put_penny(user_sub, held)
    return held


def check_penny_claims(claims: dict[str, Any], user_sub: str, penny_client_id: str) -> None:
    if claims.get("sub") != user_sub:
        raise TokenError(403, "Penny's token is for a different user.")
    actor = get_current_actor(claims)
    if actor is not None and actor != penny_client_id:
        raise TokenError(403, "This token does not belong to Penny.")
    if set(str(claims.get("scope", "")).split()) - {PENNY_SCOPE}:
        raise TokenError(403, "Penny's token may only read ghosts.")


async def ledger_context(app: FastAPI, token: str):
    """Penny's tools read the ledger through the local API, showing her token.
    In-process (ASGI), so nothing leaves the laptop."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://ghost-bills.local") as c:
        r = await c.get("/api/agent/ledger", headers={"Authorization": f"Bearer {token}"})
    if r.status_code != 200:
        raise TokenError(r.status_code, r.json().get("detail", "Penny could not read the ledger."))
    return context_from(r.json())
