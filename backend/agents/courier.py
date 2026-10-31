"""Courier: the only component that can send an email, behind three locks.

Lock 1 (Penny): Penny only ever holds a read:ghosts token. She can ask Courier,
        never send.
Lock 2 (Courier): token exchange 2 turns Penny's token into a 5-minute
        send:cancel_email token for Courier, and the send route accepts only that
        token. The job is for ONE ghost the user marked "cancel_requested", to the
        address the user typed. Gemma and Penny can't set or change it.
Lock 3 (you): the send waits for approval on your phone (CIBA, Guardian push).
        Deny or no answer means nothing is sent.

After approval: Token Vault gives a short-lived Google token, Gmail sends one
email, and the Google token is dropped. Bank data never leaves the laptop. The
only thing that does is the cancel email you approved.
"""

from __future__ import annotations

import asyncio
import logging
import re
import threading
import time
import uuid
from concurrent.futures import Future
from dataclasses import dataclass, field
from typing import Any

import httpx
from auth0_api_python import get_delegation_chain

from backend.agents import audit
from backend.agents.vault import AgentsStopped, Held
from backend.auth.tokens import TokenError
from backend.detect.scan import run_scan
from backend.models import Ghost

log = logging.getLogger("ghost_bills.courier")

SEND_SCOPE = "send:cancel_email"
MAX_SEND_TOKEN_SECONDS = 300
MIN_POLL_SECONDS = 0.01
FINAL = {"sent", "denied", "timeout", "refused", "stopped", "error"}

_EMAIL = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$")
_BINDING_OK = re.compile(r"[^A-Za-z0-9 +\-_.,:#]")

MESSAGES = {
    "asking_phone": "Check your phone to approve...",
    "sent": "Sent",
    "denied": "Not sent: you said no",
    "timeout": "Not sent: no answer in time",
    "stopped": "Not sent: agents were stopped",
}


def valid_address(address: str | None) -> bool:
    return bool(address) and len(address) <= 254 and bool(_EMAIL.match(address))


def domain_of(address: str) -> str:
    return address.rsplit("@", 1)[-1].lower()


def binding_message(domain: str, ghost_name: str) -> str:
    """CIBA allows up to 64 characters of letters, digits, spaces and +-_.,:#."""
    text = _BINDING_OK.sub("", f"Send cancel email to {domain} about {ghost_name}")
    return text[:60].rstrip()


@dataclass
class Job:
    request_id: str
    ghost_id: str
    user_sub: str
    asked_by: str
    to_address: str = field(default="", repr=False)
    penny_token: str = field(default="", repr=False)
    subject: str = field(default="", repr=False)
    body: str = field(default="", repr=False)
    ghost_name: str = ""
    state: str = "waiting"
    message: str = "Courier is getting ready..."
    future: Future | None = field(default=None, repr=False)

    def public(self) -> dict[str, Any]:
        return {"request_id": self.request_id, "ghost_id": self.ghost_id, "state": self.state,
                "message": self.message,
                "recipient_domain": domain_of(self.to_address) if self.to_address else None}

    def finish(self, state: str, message: str | None = None) -> None:
        self.state = state
        self.message = message or MESSAGES.get(state, state)


class Worker:
    """Courier's own event loop, so a 2-minute wait for your phone never blocks a request."""

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, name="courier", daemon=True).start()

    def submit(self, coro) -> Future:
        return asyncio.run_coroutine_threadsafe(coro, self.loop)


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
        self.jobs: dict[str, Job] = {}
        self._typed: dict[str, str] = {}  # ghost id -> address the USER typed (memory only)
        self._worker: Worker | None = None

    @property
    def rt(self):
        return self.app.state.agents

    @property
    def worker(self) -> Worker:
        if self._worker is None:
            self._worker = Worker()
        return self._worker

    # --- only the user's own form calls this ------------------------------------------

    def remember_typed_address(self, ghost_id: str, address: str) -> None:
        if not valid_address(address):
            raise ValueError("That doesn't look like an email address.")
        self._typed[ghost_id] = address

    # --- the one tool -------------------------------------------------------------------

    def send_cancel_email(self, ghost_id: str, to_address: str, *, user_sub: str, penny: Held,
                          asked_by: str) -> Job:
        """Courier's only tool. Starts one job, or refuses with a plain reason."""
        job = Job(uuid.uuid4().hex, ghost_id, user_sub, asked_by, to_address=to_address,
                  penny_token=penny.token)
        refusal = self._precheck(job)
        audit.start(job.request_id, asked_by=asked_by, acted_by="Courier", on_behalf_of=user_sub,
                    ghost_id=job.ghost_id,
                    recipient_domain=domain_of(to_address) if valid_address(to_address) else None,
                    scope=SEND_SCOPE)
        self.jobs[job.request_id] = job
        if refusal:
            job.finish("refused", refusal)
            job.penny_token = ""
            audit.update(job.request_id, outcome="refused", outcome_at=audit.now(), note=refusal)
            return job
        job.future = self.worker.submit(self._run(job))
        return job

    def request_for(self, ghost_id: str, *, user_sub: str, penny: Held, asked_by: str) -> Job:
        """Penny's request_send: she names a ghost. The address can only be the one you typed."""
        ghost = find_ghost(ghost_id)
        gid = ghost.id if ghost else ghost_id
        return self.send_cancel_email(gid, self._typed.get(gid, ""), user_sub=user_sub,
                                      penny=penny, asked_by=asked_by)

    def _precheck(self, job: Job) -> str | None:
        if self.rt.tokens.stopped:
            return "Agents are stopped. Log in again to start them."
        ghost = find_ghost(job.ghost_id)
        if ghost is None:
            return "There is no ghost with that name."
        job.ghost_id, job.ghost_name = ghost.id, ghost.display_name
        if ghost.status != "cancel_requested":
            return "You haven't asked to cancel this one. Use 'Send with Gmail' on it first."
        if not valid_address(job.to_address) or self._typed.get(ghost.id) != job.to_address:
            return "Only an address you typed in 'Send with Gmail' can be used."
        if ghost.cancel_email is None:
            return "This ghost has no cancel email."
        if any(j.ghost_id == ghost.id and j.state not in FINAL and j is not job
               for j in self.jobs.values()):
            return "Courier is already waiting for your approval on this one."
        job.subject, job.body = ghost.cancel_email.subject, ghost.cancel_email.body
        return None

    # --- the job --------------------------------------------------------------------------

    async def _run(self, job: Job) -> None:
        rt, s = self.rt, self.rt.settings
        try:
            # Token exchange 2 (Lock 2): Penny's delegated token in, Courier's send token out.
            result = await rt.gateway.on_behalf_of(
                s.courier_client_id, s.courier_client_secret, job.penny_token,
                subject_audience=s.ledger_audience, audience=s.courier_audience, scope=SEND_SCOPE)
            claims = await rt.verifier.verify(result["access_token"], s.courier_audience,
                                              SEND_SCOPE, actor=s.courier_client_id)
            if claims.get("sub") != job.user_sub:
                raise TokenError(403, "Courier's token is for a different user.")
            expires_at = min(float(result.get("expires_at") or claims["exp"]),
                             time.time() + MAX_SEND_TOKEN_SECONDS)
            chain = get_delegation_chain(claims)
            audit.update(job.request_id, chain=(
                "you → Penny → Courier (in the token's act claim)"
                if s.penny_client_id in chain else
                "you → Penny → Courier (recorded here; the token names only Courier)"))
            rt.tokens.put_courier(job.request_id, Held(result["access_token"], claims, expires_at))
            # Courier presents its token at the guarded send route, like any other caller.
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://ghost-bills.local",
                                         timeout=s.ciba_timeout + 60) as client:
                r = await client.post("/api/courier/send", json={"request_id": job.request_id},
                                      headers={"Authorization": f"Bearer {result['access_token']}"})
            if job.state not in FINAL:
                job.finish("error", r.json().get("detail", "Courier could not send."))
        except AgentsStopped:
            job.finish("stopped")
        except TokenError as err:
            job.finish("error", err.message)
        except Exception as err:  # never log tokens: only the error type
            log.warning("courier %s failed: %s", job.request_id, type(err).__name__)
            job.finish("error", "Courier hit an error. Nothing was sent.")
        finally:
            rt.tokens.drop_courier(job.request_id)
            job.penny_token = ""
            if job.state in ("stopped", "error"):
                audit.update(job.request_id, outcome=job.state, outcome_at=audit.now(),
                             note=job.message)

    async def deliver(self, request_id: str, claims: dict[str, Any]) -> dict[str, Any]:
        """Runs only behind Lock 2 (/api/courier/send). Adds Lock 3, then sends."""
        rt, s = self.rt, self.rt.settings
        job = self.jobs.get(request_id)
        if job is None or job.state in FINAL:
            raise TokenError(404, "No waiting send job with that id.")
        if claims.get("sub") != job.user_sub:
            raise TokenError(403, "This token is for a different user.")

        # Lock 3: ask the user's phone (CIBA). Deny or no answer = nothing is sent.
        job.finish("asking_phone")
        start = await asyncio.to_thread(
            rt.gateway.start_approval, binding_message(domain_of(job.to_address), job.ghost_name),
            job.user_sub, s.courier_audience, f"openid {SEND_SCOPE}", s.ciba_timeout)
        deadline = time.monotonic() + s.ciba_timeout
        interval = float(start.get("interval", 5) or 0)
        while True:
            if rt.tokens.stopped:
                job.finish("stopped")
                return job.public()
            if time.monotonic() > deadline:
                return self._end(job, "timeout")
            await asyncio.sleep(max(interval, MIN_POLL_SECONDS))
            answer = await asyncio.to_thread(rt.gateway.poll_approval, start["auth_req_id"])
            state = answer.get("state")
            if state == "pending":
                continue
            if state == "slow_down":
                interval += 5
                continue
            if state == "denied":
                return self._end(job, "denied")
            if state == "expired":
                return self._end(job, "timeout")
            if state != "approved":
                return self._end(job, "error", "The approval failed. Nothing was sent.")
            approval = await rt.verifier.verify(answer["access_token"], s.courier_audience, SEND_SCOPE)
            if approval.get("sub") != job.user_sub:
                return self._end(job, "error", "The approval came from a different user.")
            audit.update(job.request_id, approved_at=audit.now())
            break

        # Token Vault: a short-lived Google token (Gmail send), used once and dropped.
        vault = await rt.gateway.token_vault(s.courier_client_id, s.courier_client_secret,
                                             job.penny_token, s.ledger_audience, s.google_connection)
        try:
            message_id = await asyncio.to_thread(rt.gmail.send, vault["access_token"],
                                                 job.to_address, job.subject, job.body)
        finally:
            vault.clear()  # the Google token is gone
        job.finish("sent")
        audit.update(job.request_id, outcome="sent", outcome_at=audit.now(), sent_at=audit.now(),
                     gmail_message_id=message_id, note="Google token discarded after one send.")
        return job.public()

    def _end(self, job: Job, state: str, message: str | None = None) -> dict[str, Any]:
        job.finish(state, message)
        audit.update(job.request_id, outcome=state, outcome_at=audit.now(), note=job.message)
        return job.public()

    def stop_all(self) -> None:
        for job in self.jobs.values():
            if job.state not in FINAL:
                job.finish("stopped")
                audit.update(job.request_id, outcome="stopped", outcome_at=audit.now(),
                             note=job.message)
