# Auth0 notes for Ghost Bills (researched 31 Oct 2026)

These are the real, current names from Auth0's docs and from reading the
installed SDK source. Nothing here is guessed. Where the docs are silent, the
note says so.

## Packages we use (pinned)

| Need | Package (version) | Real names |
| --- | --- | --- |
| User login in FastAPI | `auth0-fastapi==1.0.0b12` (on `auth0-server-python` 1.0.0b20) | `auth0_fastapi.config.Auth0Config`, `auth0_fastapi.auth.auth_client.AuthClient`, `auth0_fastapi.server.routes.router` + `register_auth_routes(router, config)`. Routes: `/auth/login`, `/auth/callback`, `/auth/logout`. Session: `starlette.middleware.sessions.SessionMiddleware` (needs `itsdangerous`). User and tokens: `auth_client.client.get_user(store_options=...)`, `auth_client.client.get_access_token(store_options=..., audience=..., scope=...)` |
| Verify access tokens | `auth0-api-python==1.0.0b10` | `ApiClient(ApiClientOptions(domain=..., audience=..., client_id=..., client_secret=...))`, `await api_client.verify_access_token(access_token, required_claims=[...])`. It checks signature (JWKS), `iss`, `aud`, `exp`, `nbf`. Errors: `VerifyAccessTokenError`, `AuthServerUnavailableError` |
| RFC 8693 on-behalf-of exchange | `auth0-api-python` | `await api_client.get_token_on_behalf_of(access_token, audience, scope)` returns `access_token, expires_in, expires_at, scope, token_type`. Chain helpers: `get_current_actor(claims)`, `get_delegation_chain(claims)` |
| Token Vault (Google token) | `auth0-api-python` | `await api_client.get_access_token_for_connection({"connection": "google-oauth2", "access_token": ...})`. Grant type `urn:auth0:params:oauth:grant-type:token-exchange:federated-connection-access-token` |
| CIBA (async authorization) | `auth0-python>=4.13,<5` | `auth0.authentication.back_channel_login.BackChannelLogin(domain, client_id, client_secret).back_channel_login(binding_message, login_hint, scope, requested_expiry=..., audience=...)` returns `auth_req_id, expires_in, interval`. Poll with `auth0.authentication.get_token.GetToken(...).backchannel_login(auth_req_id)` (grant `urn:openid:params:grant-type:ciba`) |

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

## Asynchronous authorization (CIBA) facts that matter

- `POST /bc-authorize` (form-encoded): `client_id`, client auth, `login_hint`,
  `scope` (must include `openid`), `audience`, `binding_message`,
  `requested_expiry`.
- `login_hint` = `{"format":"iss_sub","iss":"https://YOUR_DOMAIN/","sub":"USER_ID"}`
- **`binding_message`: required, up to 64 characters, alphanumeric plus
  `+-_.,:#` (and spaces).** A `?` is not allowed. So Ghost Bills sends
  `Send cancel email to <domain> about <ghost name>`, cleaned and cut to 60
  characters.
- `requested_expiry`: 1–259200 seconds. **≤ 300 uses mobile push** (Guardian),
  301+ uses email. Ghost Bills uses 120 seconds.
- Poll `/oauth/token` with `grant_type=urn:openid:params:grant-type:ciba` and
  `auth_req_id`, about every `interval` (≈5) seconds. Errors:
  `authorization_pending` (keep waiting), `slow_down` (wait `interval`),
  `access_denied` (denied or expired).
- The client must be first-party, confidential (`token_endpoint_auth_method`
  is not `none`) and OIDC conformant, with the **CIBA** grant enabled.
- The user must be enrolled in Guardian push (MFA). Without MFA on the tenant,
  push requests fail.

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
| **CIBA / async authorization (phone approval)** | ❌ **not on Free** | Essentials or Professional **+ AI Agents add-on** (B2C Essentials, 500 MAU: about $35 + $18 a month), or Enterprise |
| Guardian push MFA | on the tenant's MFA settings (CIBA push itself needs the plan above) | |
| On-Behalf-Of token exchange | not marked Early Access or paid in the docs | the AI Agents add-on raises its rate limit |
| Agents as principal (`sub_profile`/`client_profile`, `agent_subject_claims`) | the docs page shows a release-stage banner. **Not required** by Ghost Bills | |
| `custom_token_exchange` / `get_token_by_exchange_profile` | **Early Access**. Not used | |
| Token Vault `scope` sub-selection parameter | **Early Access**. Not used | |

So: login, Penny's read-only token and the token checks work on the Free plan.
**The phone approval (Lock 3) needs CIBA**, which needs a paid plan with the AI
Agents add-on (or a trial that includes it). Everything is built and tested
with mocks, so it's ready the moment the tenant has CIBA.

## Sources

- On-Behalf-Of token exchange: https://auth0.com/docs/secure/call-apis-on-users-behalf/on-behalf-of-token-exchange
- Agent identity in tokens (`act`, nesting): https://auth0.com/docs/ai-agents-mcp/agents-as-principal/agent-identity-in-tokens
- CIBA flow and plan note: https://auth0.com/docs/get-started/authentication-and-authorization-flow/client-initiated-backchannel-authentication-flow
- User authorization with CIBA (parameters, errors): https://auth0.com/docs/get-started/authentication-and-authorization-flow/client-initiated-backchannel-authentication-flow/user-authorization-with-ciba
- Configure CIBA: https://auth0.com/docs/get-started/applications/configure-client-initiated-backchannel-authentication
- Token Vault access token exchange: https://auth0.com/docs/secure/tokens/token-vault/access-token-exchange-with-token-vault
- FastAPI quickstart: https://auth0.com/docs/quickstart/webapp/fastapi
- `auth0-api-python`: https://github.com/auth0/auth0-api-python
- `auth0-ai-langchain`: https://pypi.org/project/auth0-ai-langchain/
- Pricing: https://auth0.com/pricing
