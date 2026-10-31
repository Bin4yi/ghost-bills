"""Auth0 settings, read from the environment (and .env if present).

No AUTH0_DOMAIN means local-only mode: no login, no agents with tokens, no
sending. Everything else in Ghost Bills works exactly as before, offline.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from backend.settings import ROOT


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """Tiny .env reader: KEY=VALUE lines, '#' comments. Never overrides real env vars."""
    if os.environ.get("GHOST_NO_DOTENV") == "1" or not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.split(" #", 1)[0].strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


@dataclass(frozen=True)
class AuthSettings:
    domain: str = ""
    client_id: str = ""
    client_secret: str = ""
    app_base_url: str = "http://localhost:5173"
    session_secret: str = ""
    login_audience: str = ""
    ledger_audience: str = ""
    courier_audience: str = ""
    penny_client_id: str = ""
    penny_client_secret: str = ""
    courier_client_id: str = ""
    courier_client_secret: str = ""
    google_connection: str = "google-oauth2"

    @property
    def enabled(self) -> bool:
        """Login is possible."""
        return bool(self.domain and self.client_id and self.client_secret and self.session_secret)

    @property
    def agents_ready(self) -> bool:
        """Penny and Courier have their own Auth0 clients."""
        return self.enabled and all([
            self.ledger_audience, self.courier_audience, self.penny_client_id,
            self.penny_client_secret, self.courier_client_id, self.courier_client_secret])

    @property
    def issuer(self) -> str:
        return f"https://{self.domain}/"

    @property
    def step_up_redirect(self) -> str:
        """Where Auth0 returns after you confirm a send by logging in again (same Web app)."""
        return f"{self.app_base_url.rstrip('/')}/auth/step-up/callback"


def load_settings() -> AuthSettings:
    load_dotenv()
    e = os.environ.get
    return AuthSettings(
        domain=e("AUTH0_DOMAIN", "").strip(),
        client_id=e("AUTH0_CLIENT_ID", ""),
        client_secret=e("AUTH0_CLIENT_SECRET", ""),
        app_base_url=e("APP_BASE_URL", "http://localhost:5173"),
        session_secret=e("SESSION_SECRET", ""),
        login_audience=e("AUTH0_AUDIENCE", ""),
        ledger_audience=e("LEDGER_AUDIENCE", ""),
        courier_audience=e("COURIER_AUDIENCE", ""),
        penny_client_id=e("PENNY_CLIENT_ID", ""),
        penny_client_secret=e("PENNY_CLIENT_SECRET", ""),
        courier_client_id=e("COURIER_CLIENT_ID", ""),
        courier_client_secret=e("COURIER_CLIENT_SECRET", ""),
        google_connection=e("GOOGLE_CONNECTION", "google-oauth2"),
    )
