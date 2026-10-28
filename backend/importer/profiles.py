"""Saved column mappings per bank, keyed by the header row."""

from __future__ import annotations

from backend import db
from backend.models import ColumnMapping


def load(signature: str) -> ColumnMapping | None:
    row = db.get_row("profiles", "signature", signature)
    return ColumnMapping.model_validate_json(row["mapping_json"]) if row else None


def save(signature: str, mapping: ColumnMapping) -> None:
    db.put("profiles", "signature", signature, mapping_json=mapping.model_dump_json())
