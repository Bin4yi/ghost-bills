"""Lock 3: you confirm one send by logging in again (a fresh login).

The Free plan has neither CIBA nor MFA, so the approval is a fresh Auth0 login
on the existing Ghost Bills Web app with:
- max_age = 0 and prompt = login (always a real login, never a remembered session),
- state and nonce made for ONE pending send request, plus PKCE.

On the way back the new ID token must show the same user as the session, an
`auth_time` within the last 2 minutes, and the nonce and state of this request.
The request must not be expired or already used. Only then does Courier send.

This proves you are here and that you confirmed this one request. It is not a
second factor: with MFA on a paid plan, add `acr_values` and check `amr`.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

from backend.auth.config import AuthSettings

APPROVAL_SECONDS = 120   # a pending request expires after 2 minutes
AUTH_TIME_MAX_AGE = 120  # the fresh login must have happened in the last 2 minutes
CLOCK_SKEW = 10


class StepUpRefused(Exception):
    """The approval didn't pass. `outcome` is what the audit log records."""

    def __init__(self, outcome: str, reason: str) -> None:
        super().__init__(reason)
        self.outcome = outcome
        self.reason = reason


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


@dataclass
class Pending:
    """One send waiting for your approval. Secrets never leave the server."""
    request_id: str
    ghost_id: str
    user_sub: str
    asked_by: str
    to_address: str = field(default="", repr=False)
    subject: str = field(default="", repr=False)
    body: str = field(default="", repr=False)
    penny_token: str = field(default="", repr=False)  # only while sending
    ghost_name: str = ""
    state: str = field(default_factory=lambda: secrets.token_urlsafe(32), repr=False)
    nonce: str = field(default_factory=lambda: secrets.token_urlsafe(32), repr=False)
    verifier: str = field(default_factory=lambda: secrets.token_urlsafe(48), repr=False)
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    used: bool = False
    status: str = "needs_approval"
    message: str = "Confirm by logging in again"

    def __post_init__(self) -> None:
        if not self.expires_at:
            self.expires_at = self.created_at + APPROVAL_SECONDS

    def expired(self, now: float | None = None) -> bool:
        return (now or time.time()) > self.expires_at

    def public(self) -> dict[str, Any]:
        from backend.agents.courier import domain_of
        open_ = self.status == "needs_approval" and not self.used and not self.expired()
        return {"request_id": self.request_id, "ghost_id": self.ghost_id, "state": self.status,
                "message": self.message,
                "recipient_domain": domain_of(self.to_address) if self.to_address else None,
                "expires_in": max(0, int(self.expires_at - time.time())) if open_ else 0,
                "step_up_url": f"/auth/step-up/{self.request_id}" if open_ else None}


def authorize_url(settings: AuthSettings, p: Pending) -> str:
    """The Auth0 /authorize URL for this one request (fresh login, PKCE)."""
    challenge = _b64(hashlib.sha256(p.verifier.encode()).digest())
    params = {
        "response_type": "code",
        "client_id": settings.client_id,
        "redirect_uri": settings.step_up_redirect,
        "scope": "openid",
        "max_age": "0",
        "prompt": "login",
        "state": p.state,
        "nonce": p.nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return f"https://{settings.domain}/authorize?{urlencode(params)}"


def check_claims(claims: dict[str, Any], p: Pending, session_sub: str | None,
                 now: float | None = None) -> None:
    """The step-up rules. Raises StepUpRefused with a plain reason."""
    now = now or time.time()
    if claims.get("nonce") != p.nonce:
        raise StepUpRefused("failed", "the approval didn't match this request")
    if claims.get("sub") != p.user_sub or session_sub != p.user_sub:
        raise StepUpRefused("failed", "a different user approved it")
    auth_time = claims.get("auth_time")
    if not isinstance(auth_time, (int, float)):
        raise StepUpRefused("failed", "the login time is missing")
    if now - auth_time > AUTH_TIME_MAX_AGE or auth_time > now + CLOCK_SKEW:
        raise StepUpRefused("failed", "the login was too long ago")
