"""Check access tokens with Auth0's SDK, and keep raw tokens out of logs.

Signature (JWKS), issuer, audience, expiry and not-before are checked by
auth0-api-python's `verify_access_token`. Scope and the acting agent are
checked here.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Awaitable, Callable

from auth0_api_python import ApiClient, ApiClientOptions, get_current_actor, get_delegation_chain

from backend.auth.config import AuthSettings

Fetch = Callable[[str], Awaitable[Any]]


class TokenError(Exception):
    """A refused token. `status` is 401 (who are you?) or 403 (not allowed)."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def scopes(claims: dict[str, Any]) -> set[str]:
    return set(str(claims.get("scope", "")).split())


def public_claims(claims: dict[str, Any] | None) -> dict[str, Any] | None:
    """What the token inspector may show: decoded claims only, never the token."""
    if not claims:
        return None
    return {"sub": claims.get("sub"), "act": claims.get("act"), "scope": claims.get("scope"),
            "aud": claims.get("aud"), "exp": claims.get("exp"),
            "chain": get_delegation_chain(claims)}


def _plain(err: Exception) -> tuple[int, str]:
    text = str(err).lower()
    if "expired" in text or "exp" in text.split():
        return 401, "This token has expired."
    if "audience" in text or "aud" in text.split():
        return 403, "This token is for a different API."
    if "issuer" in text or "iss" in text.split():
        return 401, "This token was not issued by this Auth0 tenant."
    if "signature" in text or "jwks" in text or "kid" in text:
        return 401, "This token's signature is not valid."
    return 401, "This token is not valid."


class Verifier:
    """One auth0-api-python ApiClient per audience."""

    def __init__(self, settings: AuthSettings, custom_fetch: Fetch | None = None) -> None:
        self.settings = settings
        self.custom_fetch = custom_fetch
        self._clients: dict[str, ApiClient] = {}

    def client(self, audience: str) -> ApiClient:
        if audience not in self._clients:
            self._clients[audience] = ApiClient(ApiClientOptions(
                domain=self.settings.domain, audience=audience, dpop_enabled=False,
                custom_fetch=self.custom_fetch))
        return self._clients[audience]

    async def verify(self, token: str, audience: str, scope: str | None = None,
                     actor: str | None = None) -> dict[str, Any]:
        """Return the claims, or raise TokenError with a plain message."""
        if not self.settings.enabled or not audience:
            raise TokenError(401, "Agents are not set up on this laptop (no Auth0 settings).")
        import httpx
        from auth0_api_python.errors import VerifyAccessTokenError
        try:
            claims = await self.client(audience).verify_access_token(token)
        except httpx.HTTPError as err:  # discovery/JWKS unreachable
            raise TokenError(503, "Auth0 can't be reached to check this token.") from err
        except VerifyAccessTokenError as err:
            raise TokenError(*_plain(err)) from err
        except Exception as err:  # malformed tokens and the like
            raise TokenError(401, "This token is not valid.") from err
        if scope and scope not in scopes(claims):
            raise TokenError(403, f"This token does not allow '{scope}'.")
        if actor is not None and get_current_actor(claims) != actor:
            raise TokenError(403, "This token belongs to a different agent.")
        return claims

    # --- ID tokens from the step-up login (signature, iss, aud = the Web app, exp) ----------

    async def _fetch(self, url: str) -> dict[str, Any]:
        if self.custom_fetch:
            data = await self.custom_fetch(url)
            return data.json() if hasattr(data, "json") else data
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.json()

    async def verify_id_token(self, id_token: str) -> dict[str, Any]:
        """Check the step-up ID token's signature (JWKS), issuer, audience and expiry.
        The confirmation rules (nonce, sub, auth_time) are checked by the caller."""
        import jwt
        try:
            meta = await self._fetch(f"https://{self.settings.domain}/.well-known/openid-configuration")
            jwks = await self._fetch(meta["jwks_uri"])
        except Exception as err:
            raise TokenError(503, "Auth0 can't be reached to check the approval.") from err
        try:
            kid = jwt.get_unverified_header(id_token).get("kid")
            jwk = next(k for k in jwks.get("keys", []) if k.get("kid") == kid)
            return jwt.decode(id_token, jwt.PyJWK(jwk).key, algorithms=["RS256"],
                              audience=self.settings.client_id, issuer=self.settings.issuer,
                              leeway=10, options={"require": ["exp", "iat", "sub"]})
        except Exception as err:
            raise TokenError(401, "The approval token is not valid.") from err


# --- keep tokens out of logs --------------------------------------------------

_JWT = re.compile(r"eyJ[\w-]{6,}\.[\w-]{6,}\.[\w-]*")


def redact(text: str) -> str:
    return _JWT.sub("[token removed]", text)


class RedactTokens(logging.Filter):
    """Last line of defence: no log line ever carries a raw JWT."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if _JWT.search(msg):
            record.msg, record.args = redact(msg), None
        return True


def install_log_redaction() -> None:
    """Redact JWTs in every log record from every logger (filters on named loggers
    would miss records created by their child loggers)."""
    old = logging.getLogRecordFactory()
    if getattr(old, "_ghost_bills_redacts", False):
        return

    def factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = old(*args, **kwargs)
        try:
            msg = record.getMessage()
        except Exception:
            return record
        if _JWT.search(msg):
            record.msg, record.args = redact(msg), None
        return record

    factory._ghost_bills_redacts = True  # type: ignore[attr-defined]
    logging.setLogRecordFactory(factory)
