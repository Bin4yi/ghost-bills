"""User login with Auth0 (auth0-fastapi). Optional: without settings, nothing is mounted.

The SDK keeps the session (and the user's tokens) in an encrypted cookie
(`_a0_session`, sealed with SESSION_SECRET). The server never writes tokens to
the database or to logs.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, Response
from starlette.middleware.sessions import SessionMiddleware

from backend.auth.config import AuthSettings

LOGIN_SCOPE = "openid profile email"


def install(app: FastAPI, settings: AuthSettings) -> None:
    """Mount /auth/login, /auth/callback, /auth/logout when Auth0 is configured."""
    app.state.auth_settings = settings
    app.state.auth_client = None
    if not settings.enabled:
        return
    from auth0_fastapi.auth.auth_client import AuthClient
    from auth0_fastapi.config import Auth0Config
    from auth0_fastapi.server.routes import register_auth_routes, router

    config = Auth0Config(
        domain=settings.domain,
        client_id=settings.client_id,
        client_secret=settings.client_secret,
        app_base_url=settings.app_base_url,
        secret=settings.session_secret,
        audience=settings.login_audience or None,
        authorization_params={"scope": LOGIN_SCOPE},
    )
    app.state.config = config
    app.state.auth_client = AuthClient(config)
    add_clock_leeway(app.state.auth_client.client)
    app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)
    register_auth_routes(router, config)
    app.include_router(router)


CLOCK_LEEWAY_SECONDS = 60


def add_clock_leeway(server_client: Any, seconds: int = CLOCK_LEEWAY_SECONDS) -> None:
    """auth0-server-python 1.0.0b20 (pinned) checks the login ID token with zero clock
    tolerance, so a laptop clock a few seconds behind Auth0 fails every login with
    "The token is not yet valid (iat)". This is the same check (signature, audience,
    RS256, issuer still compared by the SDK afterwards) with the usual 60 s leeway."""
    import jwt

    async def verify_and_decode(token: str, jwks: dict, audience: str | None = None) -> dict:
        kid = jwt.get_unverified_header(token).get("kid")
        key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
        if key is None:
            raise ValueError(f"No matching key found in JWKS for kid: {kid}")
        kwargs: dict[str, Any] = {"algorithms": ["RS256"], "leeway": seconds,
                                  "options": {"verify_signature": True, "verify_iss": False}}
        if audience:
            kwargs["audience"] = audience
        return jwt.decode(token, jwt.PyJWK.from_dict(key).key, **kwargs)

    server_client._verify_and_decode_jwt = verify_and_decode


def store(request: Request, response: Response) -> dict[str, Any]:
    return {"request": request, "response": response}


async def current_user(request: Request, response: Response) -> dict[str, Any] | None:
    client = getattr(request.app.state, "auth_client", None)
    if client is None:
        return None
    try:
        return await client.client.get_user(store_options=store(request, response))
    except Exception:  # an old or broken cookie means "logged out", never an error page
        return None


async def user_access_token(request: Request, response: Response) -> str | None:
    """The logged-in user's access token for the login API. Used only for Penny's
    exchange, in memory. Never returned from the API or logged."""
    client = getattr(request.app.state, "auth_client", None)
    settings: AuthSettings = request.app.state.auth_settings
    if client is None:
        return None
    try:
        return await client.client.get_access_token(
            store_options=store(request, response), audience=settings.login_audience or None)
    except Exception:
        return None
