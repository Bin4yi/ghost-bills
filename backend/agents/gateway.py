"""Every call Ghost Bills makes to Auth0 for its agents, in one place.

Production uses Auth0's SDKs. Tests swap in a fake with the same methods, so
no test ever touches the network.
"""

from __future__ import annotations

from typing import Any, Protocol

from backend.auth.config import AuthSettings
from backend.auth.tokens import TokenError


class Gateway(Protocol):
    async def on_behalf_of(self, client_id: str, client_secret: str, subject_token: str,
                           subject_audience: str, audience: str, scope: str) -> dict[str, Any]: ...

    async def token_vault(self, client_id: str, client_secret: str, subject_token: str,
                          subject_audience: str, connection: str) -> dict[str, Any]: ...

    async def exchange_code(self, code: str, code_verifier: str, redirect_uri: str) -> dict[str, Any]: ...


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

    async def exchange_code(self, code: str, code_verifier: str, redirect_uri: str) -> dict[str, Any]:
        """Step-up callback: the authorization code (PKCE) for the Web app's ID token.
        `authenticated_post` adds the Web app's client secret (it's a confidential client)."""
        import asyncio

        from auth0.authentication.get_token import GetToken
        from auth0.exceptions import Auth0Error
        client = GetToken(self.s.domain, self.s.client_id, client_secret=self.s.client_secret)
        data = {"client_id": self.s.client_id, "grant_type": "authorization_code", "code": code,
                "code_verifier": code_verifier, "redirect_uri": redirect_uri}
        try:
            return await asyncio.to_thread(client.authenticated_post,
                                           f"https://{self.s.domain}/oauth/token", data)
        except Auth0Error as err:
            raise TokenError(401, "Auth0 did not accept the approval.") from err
