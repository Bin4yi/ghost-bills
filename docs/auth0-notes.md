# Auth0 notes for Ghost Bills (researched 31 Oct 2026)

These are the real, current names from Auth0's docs and from reading the
installed SDK source. Nothing here is guessed. Where the docs are silent, the
note says so.

## Packages we use (pinned)

| Need | Package (version) | Real names |
| --- | --- | --- |
| User login in FastAPI | `auth0-fastapi==1.0.0b12` (on `auth0-server-python` 1.0.0b20) | `auth0_fastapi.config.Auth0Config`, `auth0_fastapi.auth.auth_client.AuthClient`, `auth0_fastapi.server.routes.router` + `register_auth_routes(router, config)`. Routes: `/auth/login`, `/auth/callback`, `/auth/logout`. Session: `starlette.middleware.sessions.SessionMiddleware` (needs `itsdangerous`). User and tokens: `auth_client.client.get_user(store_options=...)`, `auth_client.client.get_access_token(store_options=..., audience=..., scope=...)` |
| Verify access tokens | `auth0-api-python==1.0.0b10` | `ApiClient(ApiClientOptions(domain=..., audience=..., client_id=..., client_secret=...))`, `await api_client.verify_access_token(access_token, required_claims=[...])`. It checks signature (JWKS), `iss`, `aud`, `exp`, `nbf`. Errors in 1.0.0b10: `VerifyAccessTokenError` (the README's `AuthServerUnavailableError` isn't in this release yet, so network failures surface as `httpx` errors) |
| RFC 8693 on-behalf-of exchange | `auth0-api-python` | `await api_client.get_token_on_behalf_of(access_token, audience, scope)` returns `access_token, expires_in, expires_at, scope, token_type`. Chain helpers: `get_current_actor(claims)`, `get_delegation_chain(claims)` |
| Token Vault (Google token) | `auth0-api-python` | `await api_client.get_access_token_for_connection({"connection": "google-oauth2", "access_token": ...})`. Grant type `urn:auth0:params:oauth:grant-type:token-exchange:federated-connection-access-token` |
| Fresh-login confirmation: code exchange | `auth0-python>=4.13,<5` | `auth0.authentication.get_token.GetToken(domain, client_id, client_secret).authenticated_post(f"https://{domain}/oauth/token", data)` with `grant_type=authorization_code`, `code`, `code_verifier` (PKCE) and `redirect_uri`. (`authorization_code_pkce()` is for public clients and doesn't send the secret, but Ghost Bills Web is confidential.) |
| Fresh-login confirmation: ID token check | `PyJWT` (already installed with the Auth0 SDKs) | `jwt.decode(id_token, PyJWK(jwk).key, algorithms=["RS256"], audience=<web client id>, issuer=<tenant>)`, using the tenant's JWKS from `/.well-known/openid-configuration` |

### Why not `auth0-ai-langchain`?

`auth0-ai-langchain` 1.0.1 (the SDK behind the "Calling APIs" and "Async
Authorization" examples) has the right helpers (`Auth0AI().with_async_authorization(...)`,
`with_token_vault(...)`, `get_async_authorization_credentials()`,
`get_credentials_from_token_vault()`). But it requires `langgraph<0.6` and
`langchain<0.4`, and Ghost Bills runs LangGraph 1.2. Installing it would
downgrade the agent stack. So Ghost Bills calls the same Auth0 endpoints through
`auth0-api-python` and `auth0-python`, which are Auth0's lower-level official SDKs.

## How the token exchange really works in Auth0 (important)

Auth0's On-Behalf-Of (OBO) token exchange is RFC 8693 on `POST /oauth/token`:

```
grant_type           = urn:ietf:params:oauth:grant-type:token-exchange
subject_token        = <the incoming user (or delegated) access token>
subject_token_type   = urn:ietf:params:oauth:token-type:access_token
requested_token_type = urn:ietf:params:oauth:token-type:access_token
audience             = <downstream API>
scope                = <space-separated scopes>
client_id / client_secret  (the agent's own client)
```

**There is no `actor_token` parameter.** The actor is the client that
authenticates the exchange. Auth0 writes it into the `act` claim. So "actor =
Penny's client" means "Penny's client ID and secret sign the request".

The agent clients must be **Custom API Clients**: "`app_type` set to
`resource_server`, with `resource_server_identifier` set to the audience of the
incoming token". Each one is tied to the API whose token it receives. That's
why Ghost Bills uses one API per hop (see the README's Auth0 setup).

### Can Auth0 nest `act` (Courier → Penny → user)?

**Yes.** A delegated token can be the next `subject_token`. "Each level of `act`
is a service in the chain. The outermost `act.sub` is the current actor":

```json
{ "sub": "auth0|user", "act": { "sub": "<courier client id>", "act": { "sub": "<penny client id>" } } }
```

Limit: 5 hops / 4 nested `act` levels. The exchange fails with
`400 invalid_request` beyond that. Only the outermost `act.sub` should be used
for authorization decisions. Ghost Bills checks it, and also records the full
chain in the local audit log. If a tenant returns no nested `act`, Courier
records the chain user → Penny → Courier in the audit log instead.

Other limits: refresh tokens are **not** supported for OBO (so we re-exchange
before expiry). The OBO rate limit is 30 RPS. The exchanged token's lifetime
comes from the downstream API's settings. Ghost Bills also enforces its own
5-minute budget for Courier's token.

## Lock 3: a fresh-login confirmation (instead of CIBA or MFA)

**Why not CIBA:** CIBA (`/bc-authorize`, Guardian push approval) needs "an
Enterprise Plan or an appropriate add-on". This tenant's dashboard doesn't
offer the CIBA grant type.

**Why not step-up MFA:** MFA (Guardian push or OTP) needs a Professional or
Enterprise plan on this account.

So on the Free plan, you confirm each send with a **fresh login** on the
existing Ghost Bills Web app:

1. Ghost Bills sends you to `/authorize` with `max_age=0` and `prompt=login`
   (standard OpenID Connect: always a real login, never a remembered session),
   `scope=openid`, and a `state` and `nonce` made for one pending send, plus
   PKCE (`code_challenge`, `S256`).
2. On the callback, Ghost Bills exchanges the code and checks the new **ID
   token**: signature (JWKS), issuer, audience (= the Web app), expiry, then:
   - `nonce` and `state` belong to this pending request,
   - `sub` is the same user as the current session,
   - `auth_time` is within the last 120 seconds (OIDC requires `auth_time` when
     `max_age` is sent),
   - the request is not expired (2 minutes) and not already used (one-time).
3. Only then: Courier's token exchange → Token Vault Google token → one Gmail
   send → the Google token is dropped. A cancelled login, a failed check or
   expiry means nothing is sent, and the audit row says why
   (`approval_method = "fresh login"`, `approved_at = auth_time`).

**What it proves:** you are at the keyboard right now, and you confirmed this
one request (the state, nonce and one-time use tie the login to it). **What it
doesn't prove:** a second factor. On a plan with MFA, add
`acr_values=http://schemas.openid.net/pape/policies/2007/06/multi-factor`, a
Post-Login Action that calls `api.multifactor.enable('any', { allowRememberBrowser: false })`,
and check that `amr` contains `"mfa"`.

## Token Vault facts that matter

- Google tokens are stored when the user logs in with (or connects) the Google
  connection with Token Vault on. Auth0 refreshes the Google access token from
  the stored refresh token on each exchange.
- Backend exchange: a Custom API Client with the **Token Vault** grant enabled
  sends the user's (delegated) Auth0 access token as `subject_token` and gets a
  Google access token back (`access_token, scope, expires_in`).
- Ghost Bills asks Google only for `https://www.googleapis.com/auth/gmail.send`
  and drops the Google token right after one `users.messages.send` call.

## Plans and Early Access (check before the live demo)

| Feature | Free | Paid |
| --- | --- | --- |
| Token Vault | ✅ 2 connected apps | more on paid plans |
| CIBA / async authorization | ❌ not on Free (**not used**: replaced by a fresh-login confirmation) | Essentials or Professional + AI Agents add-on, or Enterprise |
| MFA (Guardian push or OTP) | ❌ on this account (**not used**) | Professional or Enterprise |
| Fresh login (`max_age=0`, `prompt=login`) | ✅ standard OIDC | |
| On-Behalf-Of token exchange | not marked Early Access or paid in the docs | the AI Agents add-on raises its rate limit |
| Agents as principal (`sub_profile`/`client_profile`, `agent_subject_claims`) | the docs page shows a release-stage banner. **Not required** by Ghost Bills | |
| `custom_token_exchange` / `get_token_by_exchange_profile` | **Early Access**. Not used | |
| Token Vault `scope` sub-selection parameter | **Early Access**. Not used | |

So everything Ghost Bills uses (login, both On-Behalf-Of exchanges, Token Vault
and the fresh-login confirmation) works without CIBA or MFA.

## Sources

- On-Behalf-Of token exchange: https://auth0.com/docs/secure/call-apis-on-users-behalf/on-behalf-of-token-exchange
- Agent identity in tokens (`act`, nesting): https://auth0.com/docs/ai-agents-mcp/agents-as-principal/agent-identity-in-tokens
- CIBA plan note (why it isn't used): https://auth0.com/docs/get-started/authentication-and-authorization-flow/client-initiated-backchannel-authentication-flow
- Step-up authentication for web apps (for a future plan with MFA): https://auth0.com/docs/secure/multi-factor-authentication/step-up-authentication/configure-step-up-authentication-for-web-apps
- Token Vault access token exchange: https://auth0.com/docs/secure/tokens/token-vault/access-token-exchange-with-token-vault
- FastAPI quickstart: https://auth0.com/docs/quickstart/webapp/fastapi
- `auth0-api-python`: https://github.com/auth0/auth0-api-python
- `auth0-ai-langchain`: https://pypi.org/project/auth0-ai-langchain/
- Pricing: https://auth0.com/pricing
