"""Gmail users.messages.send, with a Google token that is used once and dropped."""

from __future__ import annotations

import base64
from email.message import EmailMessage

import httpx

GMAIL_SEND = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


def build_raw(to_address: str, subject: str, body: str) -> str:
    msg = EmailMessage()
    msg["To"] = to_address
    msg["Subject"] = subject
    msg.set_content(body)
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


class GmailSender:
    def send(self, google_token: str, to_address: str, subject: str, body: str) -> str:
        """Send one email from the user's own Gmail. Returns Gmail's message id."""
        r = httpx.post(GMAIL_SEND, headers={"Authorization": f"Bearer {google_token}"},
                       json={"raw": build_raw(to_address, subject, body)}, timeout=20)
        if r.status_code >= 400:
            raise RuntimeError(f"Gmail refused the email (HTTP {r.status_code}).")
        return str(r.json().get("id", ""))
