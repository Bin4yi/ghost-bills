"""Courier: the only component that can send an email, behind three locks.

Lock 1 (Penny): Penny only ever holds a read:ghosts token. She can ask Courier,
        never send.
Lock 2 (Courier): token exchange 2 turns Penny's token into a 5-minute
        send:cancel_email token for Courier, and the send route accepts only that
        token. The job is for ONE ghost the user marked "cancel_requested", to the
        address the user typed. Gemma and Penny can't set or change it.
Lock 3 (you): the send waits until you confirm it by logging in again, for
        this one request (see backend/auth/stepup.py). Cancelled, too old, wrong
        user, expired or reused means nothing is sent.

After approval: Token Vault gives a short-lived Google token, Gmail sends one
email, and the Google token is dropped. Bank data never leaves the laptop. The
only thing that does is the cancel email you approved.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from auth0_api_python import get_delegation_chain

from backend.agents import audit
from backend.agents.vault import AgentsStopped, Held
from backend.auth.stepup import Pending
from backend.auth.tokens import TokenError
from backend.detect.scan import run_scan
from backend.models import Ghost

log = logging.getLogger("ghost_bills.courier")

SEND_SCOPE = "send:cancel_email"
APPROVAL_METHOD = "fresh login"
MAX_SEND_TOKEN_SECONDS = 300
FINAL = {"sent", "cancelled", "expired", "failed", "refused", "stopped", "error"}

_EMAIL = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$")

MESSAGES = {
    "needs_approval": "Confirm by logging in again",
    "approved": "Approved. Sending...",
    "sent": "Sent",
    "cancelled": "Not sent: approval cancelled",
    "expired": "Not sent: approval expired",
    "stopped": "Not sent: agents were stopped",
}


def valid_address(address: str | None) -> bool:
    return bool(address) and len(address) <= 254 and bool(_EMAIL.match(address))


def domain_of(address: str) -> str:
    return address.rsplit("@", 1)[-1].lower()


def plain_error(err: Exception) -> str:
    """Auth0/Gmail's own error code and message, never a token."""
    from backend.auth.tokens import redact
    code = getattr(err, "code", None) or type(err).__name__
    message = getattr(err, "message", None) or str(err)
    return redact(f"{code}: {message}")[:240]


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds")


def find_ghost(ghost_id: str | None) -> Ghost | None:
    if not ghost_id:
        return None
    ghosts = run_scan().ghosts
    exact = next((g for g in ghosts if g.id == ghost_id), None)
    if exact:
        return exact
    want = ghost_id.lower().strip()
    return next((g for g in ghosts if want and want in g.display_name.lower()), None)


class Courier:
    def __init__(self, app) -> None:
        self.app = app
        self.jobs: dict[str, Pending] = {}
        self._typed: dict[str, str] = {}  # ghost id -> address the USER typed (memory only)

    @property
    def rt(self):
        return self.app.state.agents

    # --- only the user's own form calls this ------------------------------------------

    def remember_typed_address(self, ghost_id: str, address: str) -> None:
        if not valid_address(address):
            raise ValueError("That doesn't look like an email address.")
        self._typed[ghost_id] = address

    # --- the one tool: prepare a send that waits for your approval ---------------------

    def send_cancel_email(self, ghost_id: str, to_address: str, *, user_sub: str,
                          asked_by: str) -> Pending:
        """Courier's only tool. Creates one pending send (2 minutes), or refuses."""
        p = Pending(uuid.uuid4().hex, ghost_id, user_sub, asked_by, to_address=to_address)
        refusal = self._precheck(p)
        audit.start(p.request_id, asked_by=asked_by, acted_by="Courier", on_behalf_of=user_sub,
                    ghost_id=p.ghost_id,
                    recipient_domain=domain_of(to_address) if valid_address(to_address) else None,
                    scope=SEND_SCOPE, approval_method=APPROVAL_METHOD)
        self.jobs[p.request_id] = p
        if refusal:
            self._end(p, "refused", refusal)
        return p

    def request_for(self, ghost_id: str, *, user_sub: str, asked_by: str) -> Pending:
        """Penny's request_send: she names a ghost. The address can only be the one you typed."""
        ghost = find_ghost(ghost_id)
        gid = ghost.id if ghost else ghost_id
        return self.send_cancel_email(gid, self._typed.get(gid, ""), user_sub=user_sub,
                                      asked_by=asked_by)

    def _precheck(self, p: Pending) -> str | None:
        if self.rt.tokens.stopped:
            return "Agents are stopped. Log in again to start them."
        ghost = find_ghost(p.ghost_id)
        if ghost is None:
            return "There is no ghost with that name."
        p.ghost_id, p.ghost_name = ghost.id, ghost.display_name
        if ghost.status != "cancel_requested":
            return "You haven't asked to cancel this one. Use 'Send with Gmail' on it first."
        if not valid_address(p.to_address) or self._typed.get(ghost.id) != p.to_address:
            return "Only an address you typed in 'Send with Gmail' can be used."
        if ghost.cancel_email is None:
            return "This ghost has no cancel email."
        if any(j.ghost_id == ghost.id and j.status == "needs_approval" and not j.used
               and not j.expired() for j in self.jobs.values()):
            return "There's already a send waiting for your approval on this one."
        p.subject, p.body = ghost.cancel_email.subject, ghost.cancel_email.body
        return None

    # --- after the step-up callback ------------------------------------------------------

    def find_by_state(self, state: str | None) -> Pending | None:
        if not state:
            return None
        return next((p for p in self.jobs.values() if p.state == state), None)

    def open_for(self, user_sub: str) -> list[Pending]:
        return [p for p in self.jobs.values() if p.user_sub == user_sub and not p.used
                and p.status == "needs_approval" and not p.expired()]

    def refuse(self, p: Pending, outcome: str, reason: str) -> None:
        """Cancelled login, failed checks or expiry: nothing is sent, the audit says why."""
        p.used = True
        message = {"cancelled": MESSAGES["cancelled"], "expired": MESSAGES["expired"]}.get(
            outcome, f"Not sent: approval failed ({reason})")
        self._end(p, outcome, message, note=reason)

    async def approve_and_send(self, p: Pending, id_claims: dict[str, Any], penny: Held) -> None:
        """Your confirmation passed. One-time: mark used, then Lock 2, Token Vault and Gmail."""
        rt, s = self.rt, self.rt.settings
        p.used = True
        p.status, p.message = "approved", MESSAGES["approved"]
        audit.update(p.request_id, approved_at=iso(float(id_claims["auth_time"])))
        try:
            rt.tokens.check_running()
            # Token exchange 2 (Lock 2): Penny's delegated token in, Courier's send token out.
            result = await rt.gateway.on_behalf_of(
                s.courier_client_id, s.courier_client_secret, penny.token,
                subject_audience=s.ledger_audience, audience=s.courier_audience, scope=SEND_SCOPE)
            claims = await rt.verifier.verify(result["access_token"], s.courier_audience,
                                              SEND_SCOPE, actor=s.courier_client_id)
            if claims.get("sub") != p.user_sub:
                raise TokenError(403, "Courier's token is for a different user.")
            expires_at = min(float(result.get("expires_at") or claims["exp"]),
                             time.time() + MAX_SEND_TOKEN_SECONDS)
            chain = get_delegation_chain(claims)
            audit.update(p.request_id, chain=(
                "you → Penny → Courier (in the token's act claim)"
                if s.penny_client_id in chain else
                "you → Penny → Courier (recorded here; the token names only Courier)"))
            rt.tokens.put_courier(p.request_id, Held(result["access_token"], claims, expires_at))
            p.penny_token = penny.token
            # Courier presents its token at the guarded send route, like any other caller.
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://ghost-bills.local",
                                         timeout=60) as client:
                r = await client.post("/api/courier/send", json={"request_id": p.request_id},
                                      headers={"Authorization": f"Bearer {result['access_token']}"})
            if p.status not in FINAL:
                self._end(p, "error", f"Not sent: {r.json().get('detail', 'Courier could not send.')}")
        except AgentsStopped:
            self._end(p, "stopped", MESSAGES["stopped"])
        except TokenError as err:
            self._end(p, "error", f"Not sent: {err.message}")
        except Exception as err:  # never log tokens: only the error type
            log.warning("courier %s failed: %s", p.request_id, type(err).__name__)
            self._end(p, "error", "Not sent: Courier hit an error.")
        finally:
            rt.tokens.drop_courier(p.request_id)
            p.penny_token = ""

    async def deliver(self, request_id: str, claims: dict[str, Any]) -> dict[str, Any]:
        """Runs only behind Lock 2 (/api/courier/send), and only for an approved request."""
        rt, s = self.rt, self.rt.settings
        p = self.jobs.get(request_id)
        if p is None or p.status != "approved":
            raise TokenError(403, "This send was not approved by you.")
        if claims.get("sub") != p.user_sub:
            raise TokenError(403, "This token is for a different user.")
        # Token Vault: a short-lived Google token (Gmail send), used once and dropped.
        try:
            vault = await rt.gateway.token_vault(s.courier_client_id, s.courier_client_secret,
                                                 p.penny_token, s.ledger_audience,
                                                 s.google_connection)
        except Exception as err:
            raise TokenError(502, f"Auth0 didn't give Courier a Google token ({plain_error(err)}). "
                                  "Press 'Connect Gmail' once, then try again") from err
        try:
            import asyncio
            message_id = await asyncio.to_thread(rt.gmail.send, vault["access_token"],
                                                 p.to_address, p.subject, p.body)
        except Exception as err:
            raise TokenError(502, f"Gmail didn't send it ({plain_error(err)})") from err
        finally:
            vault.clear()  # the Google token is gone
        self._end(p, "sent", MESSAGES["sent"], sent=True, gmail_message_id=message_id,
                  note="Google token discarded after one send.")
        return p.public()

    def _end(self, p: Pending, status: str, message: str, *, sent: bool = False,
             note: str | None = None, gmail_message_id: str | None = None) -> None:
        p.status, p.message = status, message
        fields: dict[str, Any] = {"outcome": status, "outcome_at": audit.now(),
                                  "note": note or message}
        if sent:
            fields.update(sent_at=audit.now(), gmail_message_id=gmail_message_id)
        audit.update(p.request_id, **fields)

    def stop_all(self) -> None:
        for p in self.jobs.values():
            if p.status in ("needs_approval", "approved") and not p.used:
                p.used = True
                self._end(p, "stopped", MESSAGES["stopped"])

