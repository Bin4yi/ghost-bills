"""SQLite storage. One file, no server."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any, Iterator

from backend import settings
from backend.models import Transaction

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL,
    description_raw TEXT NOT NULL,
    merchant_key TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    currency TEXT NOT NULL,
    original_amount_cents INTEGER,
    original_currency TEXT
);
CREATE TABLE IF NOT EXISTS uploads (
    upload_id TEXT PRIMARY KEY,
    raw_text TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS imports (
    id INTEGER PRIMARY KEY,
    signature TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    mapping_json TEXT NOT NULL,
    needs_user INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS profiles (
    signature TEXT PRIMARY KEY,
    mapping_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS answers (
    question_id TEXT PRIMARY KEY,
    answer TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS categories (
    merchant_key TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    source TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS essentials (
    merchant_key TEXT PRIMARY KEY,
    essential INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS ghost_status (
    ghost_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    cancelled_at TEXT
);
CREATE TABLE IF NOT EXISTS enrich_cache (
    key TEXT PRIMARY KEY,
    json TEXT NOT NULL,
    text_source TEXT NOT NULL,
    seconds REAL NOT NULL
);
"""


def db_path() -> Path:
    return settings.DB_PATH


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    con = sqlite3.connect(db_path())
    con.row_factory = sqlite3.Row
    try:
        con.executescript(SCHEMA)
        yield con
        con.commit()
    finally:
        con.close()


# --- transactions ---------------------------------------------------------

def replace_transactions(txs: list[Transaction]) -> int:
    """One statement at a time: a new import replaces the old one."""
    with connect() as con:
        con.execute("DELETE FROM transactions")
        con.executemany(
            "INSERT INTO transactions (date, description_raw, merchant_key, amount_cents,"
            " currency, original_amount_cents, original_currency) VALUES (?,?,?,?,?,?,?)",
            [(t.date.isoformat(), t.description_raw, t.merchant_key, t.amount_cents,
              t.currency, t.original_amount_cents, t.original_currency) for t in txs],
        )
    return len(txs)


def load_transactions() -> list[Transaction]:
    with connect() as con:
        rows = con.execute("SELECT * FROM transactions ORDER BY date, id").fetchall()
    return [Transaction(id=r["id"], date=date.fromisoformat(r["date"]),
                        description_raw=r["description_raw"], merchant_key=r["merchant_key"],
                        amount_cents=r["amount_cents"], currency=r["currency"],
                        original_amount_cents=r["original_amount_cents"],
                        original_currency=r["original_currency"]) for r in rows]


# --- small key/value helpers --------------------------------------------

def put(table: str, key_col: str, key: str, **values: Any) -> None:
    cols = [key_col, *values]
    marks = ",".join("?" for _ in cols)
    with connect() as con:
        con.execute(f"INSERT OR REPLACE INTO {table} ({','.join(cols)}) VALUES ({marks})",
                    [key, *values.values()])


def delete(table: str, key_col: str, key: str) -> None:
    with connect() as con:
        con.execute(f"DELETE FROM {table} WHERE {key_col} = ?", [key])


def all_rows(table: str) -> list[dict[str, Any]]:
    with connect() as con:
        return [dict(r) for r in con.execute(f"SELECT * FROM {table}").fetchall()]


def get_row(table: str, key_col: str, key: str) -> dict[str, Any] | None:
    with connect() as con:
        r = con.execute(f"SELECT * FROM {table} WHERE {key_col} = ?", [key]).fetchone()
    return dict(r) if r else None


def save_import(signature: str, raw_text: str, mapping: dict, needs_user: bool) -> None:
    with connect() as con:
        con.execute("DELETE FROM imports")
        con.execute("INSERT INTO imports (signature, raw_text, mapping_json, needs_user)"
                    " VALUES (?,?,?,?)", [signature, raw_text, json.dumps(mapping), int(needs_user)])


def last_import() -> dict[str, Any] | None:
    with connect() as con:
        r = con.execute("SELECT * FROM imports ORDER BY id DESC LIMIT 1").fetchone()
    return dict(r) if r else None
