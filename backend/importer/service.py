"""Import flow used by the API: preview -> user confirms mapping -> commit."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from backend import db
from backend.importer import csv_import, profiles
from backend.models import ColumnMapping, ImportPreview


def preview(data: bytes) -> ImportPreview:
    text = csv_import.decode(data)
    header, rows = csv_import.read_table(text)
    signature = csv_import.header_signature(header)
    saved = profiles.load(signature)
    mapping = saved or csv_import.guess_mapping(header, rows)
    upload_id = uuid.uuid4().hex
    db.put("uploads", "upload_id", upload_id, raw_text=text,
           created_at=datetime.now(timezone.utc).isoformat())
    needs_user = mapping is not None and mapping.date_order is None
    message = None
    if mapping is None:
        message = "I could not guess the columns. Please pick them below."
    elif needs_user:
        message = "Every date could be day/month or month/day. Please pick the date order."
    return ImportPreview(upload_id=upload_id, signature=signature, headers=header,
                         rows=rows[:5], mapping=mapping, needs_user=needs_user,
                         from_profile=saved is not None, message=message)


def commit(upload_id: str, mapping: ColumnMapping) -> dict:
    row = db.get_row("uploads", "upload_id", upload_id)
    if row is None:
        raise csv_import.ImportError_("Upload expired. Please choose the file again.")
    return import_text(row["raw_text"], mapping)


def import_text(text: str, mapping: ColumnMapping) -> dict:
    """Parse and store. An unclear date order is imported as day/month and
    turned into a question card, so the user can fix it later."""
    header, rows = csv_import.read_table(text)
    signature = csv_import.header_signature(header)
    needs_user = mapping.date_order is None
    txs = csv_import.build_transactions(rows, mapping, date_order=mapping.date_order or "dmy")
    count = db.replace_transactions(txs)
    profiles.save(signature, mapping)
    db.save_import(signature, text, mapping.model_dump(), needs_user)
    return {"imported": count, "needs_user": needs_user, "signature": signature}


def reimport_with_order(order: str) -> dict | None:
    """Used when the user answers the date-order question."""
    last = db.last_import()
    if last is None:
        return None
    mapping = ColumnMapping.model_validate_json(last["mapping_json"])
    mapping.date_order = order  # type: ignore[assignment]
    return import_text(last["raw_text"], mapping)
