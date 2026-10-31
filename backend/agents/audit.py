"""Local audit log of what the agents did (SQLite). No tokens, no email bodies,
and only the recipient's domain, never the full address."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend import db

FIELDS = ("asked_by", "acted_by", "on_behalf_of", "ghost_id", "recipient_domain", "scope",
          "chain", "approval_method", "requested_at", "approved_at", "outcome", "outcome_at", "sent_at",
          "gmail_message_id", "note")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def start(request_id: str, **fields: Any) -> None:
    row = {k: fields.get(k) for k in FIELDS}
    row["requested_at"] = row["requested_at"] or now()
    db.put("audit", "request_id", request_id, **row)


def update(request_id: str, **fields: Any) -> None:
    row = db.get_row("audit", "request_id", request_id)
    if row is None:
        return
    row.pop("request_id", None)
    row.update({k: v for k, v in fields.items() if k in FIELDS})
    db.put("audit", "request_id", request_id, **row)


def rows() -> list[dict[str, Any]]:
    return sorted(db.all_rows("audit"), key=lambda r: r["requested_at"], reverse=True)
