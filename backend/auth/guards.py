"""Who may call which route.

Two kinds of callers reach the API:
- the app's own page in your browser on this laptop (the "local UI"), and
- agents, which must show an Auth0 access token (Bearer).

Why the offline demo keeps working: the local UI never needs a token. A request
from this laptop with no Authorization header is the person at the keyboard,
exactly as before Auth0 existed. So when you are logged out (or Auth0 isn't set
up at all, or the Wi-Fi is off), every screen still works. Tokens are only
demanded from agents, and an agent that shows a token gets the full check:
signature (JWKS), issuer, audience, expiry and scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request

from backend.agents.runtime import runtime
from backend.auth.tokens import TokenError

LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}


@dataclass
class Caller:
    kind: str  # "local" or "agent"
    claims: dict[str, Any] | None = None


def _bearer(request: Request) -> str | None:
    header = request.headers.get("authorization")
    if not header:
        return None
    kind, _, token = header.partition(" ")
    if kind.lower() != "bearer" or not token.strip():
        raise HTTPException(401, "Send the token as 'Authorization: Bearer <token>'.")
    return token.strip()


def is_local(request: Request) -> bool:
    return bool(request.client) and request.client.host in LOCAL_HOSTS


def audience_for(request: Request, scope: str) -> str:
    s = runtime(request).settings
    return s.courier_audience if scope == "send:cancel_email" else s.ledger_audience


async def check_token(request: Request, token: str, scope: str, actor: str | None = None) -> dict:
    try:
        return await runtime(request).verifier.verify(token, audience_for(request, scope),
                                                      scope, actor=actor)
    except TokenError as err:
        raise HTTPException(err.status, err.message) from err


def agent_or_local(scope: str):
    """For read routes: the local UI, or an agent with a valid `scope` token."""
    async def dependency(request: Request) -> Caller:
        token = _bearer(request)
        if token:
            return Caller("agent", await check_token(request, token, scope))
        if is_local(request):
            return Caller("local")
        raise HTTPException(401, f"This route needs a token with '{scope}'.")
    return dependency


async def local_ui_only(request: Request) -> Caller:
    """For your own decisions (keep, cancel, send): agents are refused, even with a token."""
    if _bearer(request):
        raise HTTPException(403, "Only you can do this, in the app. Agents can't.")
    if not is_local(request):
        raise HTTPException(401, "Open Ghost Bills on this laptop to do this.")
    return Caller("local")


async def courier_only(request: Request) -> Caller:
    """Lock 2: only Courier's token, with send:cancel_email, may reach the send route."""
    token = _bearer(request)
    if not token:
        raise HTTPException(401, "Sending needs Courier's token.")
    rt = runtime(request)
    claims = await check_token(request, token, "send:cancel_email", actor=rt.settings.courier_client_id)
    return Caller("agent", claims)
