"""Agent tokens, held in server memory only (never the database, logs or API).

Lock 1 lives here: Penny holds one short read:ghosts token per user.
Courier holds a send token only while a single job runs.
"Stop all agents" drops everything and blocks new exchanges until the user
logs in again.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

from backend.auth.tokens import public_claims

REFRESH_MARGIN = 60  # re-exchange this many seconds before expiry


class AgentsStopped(Exception):
    """The user pressed 'Stop all agents'."""


@dataclass
class Held:
    token: str = field(repr=False)  # never printed
    claims: dict[str, Any]
    expires_at: float

    def fresh(self, now: float | None = None) -> bool:
        return (now or time.time()) < self.expires_at - REFRESH_MARGIN

    def view(self) -> dict[str, Any] | None:
        return public_claims(self.claims)


class AgentTokens:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.penny: dict[str, Held] = {}       # user sub -> Penny's delegated token
        self.courier: dict[str, Held] = {}     # request id -> Courier's send token
        self.stopped = False

    def check_running(self) -> None:
        if self.stopped:
            raise AgentsStopped("Agents are stopped. Log in again to start them.")

    def put_penny(self, user_sub: str, held: Held) -> None:
        with self._lock:
            self.check_running()
            self.penny[user_sub] = held

    def put_courier(self, request_id: str, held: Held) -> None:
        with self._lock:
            self.check_running()
            self.courier[request_id] = held

    def drop_courier(self, request_id: str) -> None:
        with self._lock:
            self.courier.pop(request_id, None)

    def stop(self) -> None:
        """Clear every agent token and block new exchanges."""
        with self._lock:
            self.penny.clear()
            self.courier.clear()
            self.stopped = True

    def resume(self) -> None:
        """Called after a fresh login."""
        with self._lock:
            self.stopped = False

    def inspector(self, user_sub: str | None) -> dict[str, Any]:
        """Decoded claims only, for the 'Who can do what right now' card."""
        with self._lock:
            penny = self.penny.get(user_sub) if user_sub else None
            courier = next((h for h in self.courier.values()
                            if user_sub and h.claims.get("sub") == user_sub), None)
            return {"stopped": self.stopped,
                    "penny": penny.view() if penny and penny.expires_at > time.time() else None,
                    "courier": courier.view() if courier and courier.expires_at > time.time() else None}
