"""Every call Ghost Bills makes to Auth0 for its agents, in one place.

Production uses Auth0's SDKs. Tests swap in a fake with the same methods, so
no test ever touches the network.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from backend.auth.config import AuthSettings


class Gateway(Protocol):
    async def on_behalf_of(self, client_id: str, client_secret: str, subject_token: str,
                           subject_audience: str, audience: str, scope: str) -> dict[str, Any]: ...

    async def token_vault(self, client_id: str, client_secret: str, subject_token: str,
                          subject_audience: str, connection: str) -> dict[str, Any]: ...

    def start_approval(self, binding_message: str, user_sub: str, audience: str, scope: str,
                       expiry: int) -> dict[str, Any]: ...

    def poll_approval(self, auth_req_id: str) -> dict[str, Any]: ...


class Auth0Gateway:
    def __init__(self, settings: AuthSettings) -> None:
        self.s = settings

    async def on_behalf_of(self, client_id: str, client_secret: str, subject_token: str,
                           subject_audience: str, audience: str, scope: str) -> dict[str, Any]:
        """RFC 8693 On-Behalf-Of exchange. The authenticating client becomes `act`."""
        from auth0_api_python import ApiClient, ApiClientOptions
        api = ApiClient(ApiClientOptions(domain=self.s.domain, audience=subject_audience,
                                         client_id=client_id, client_secret=client_secret,
                                         dpop_enabled=False))
        result = await api.get_token_on_behalf_of(subject_token, audience=audience, scope=scope)
        return dict(result)

    async def token_vault(self, client_id: str, client_secret: str, subject_token: str,
                          subject_audience: str, connection: str) -> dict[str, Any]:
        """Token Vault: an Auth0 access token in, the user's Google access token out."""
        from auth0_api_python import ApiClient, ApiClientOptions
        api = ApiClient(ApiClientOptions(domain=self.s.domain, audience=subject_audience,
                                         client_id=client_id, client_secret=client_secret,
                                         dpop_enabled=False))
        return await api.get_access_token_for_connection(
            {"connection": connection, "access_token": subject_token})

    def start_approval(self, binding_message: str, user_sub: str, audience: str, scope: str,
                       expiry: int) -> dict[str, Any]:
        """CIBA /bc-authorize. Expiry <= 300 s means Guardian push to the user's phone."""
        from auth0.authentication.back_channel_login import BackChannelLogin
        client_id, client_secret = self.s.approval_client
        login_hint = json.dumps({"format": "iss_sub", "iss": self.s.issuer, "sub": user_sub})
        return BackChannelLogin(self.s.domain, client_id, client_secret=client_secret
                                ).back_channel_login(binding_message=binding_message,
                                                     login_hint=login_hint, scope=scope,
                                                     requested_expiry=expiry, audience=audience)

    def poll_approval(self, auth_req_id: str) -> dict[str, Any]:
        """Poll /oauth/token with the CIBA grant. Returns {"state": ...}."""
        from auth0.authentication.get_token import GetToken
        from auth0.exceptions import Auth0Error
        client_id, client_secret = self.s.approval_client
        try:
            token = GetToken(self.s.domain, client_id, client_secret=client_secret
                             ).backchannel_login(auth_req_id)
        except Auth0Error as err:
            code = getattr(err, "error_code", "") or ""
            if code == "authorization_pending":
                return {"state": "pending"}
            if code == "slow_down":
                return {"state": "slow_down"}
            if code in ("access_denied",):
                return {"state": "denied"}
            if code in ("expired_token", "invalid_grant"):
                return {"state": "expired"}
            return {"state": "error", "code": code or "unknown"}
        return {"state": "approved", "access_token": token.get("access_token")}
