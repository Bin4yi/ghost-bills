"""Ledger: reads the local SQLite statement. No Auth0 token, never online."""

from __future__ import annotations

from datetime import date
from typing import Any

from backend import db
from backend.agent.tools import Context
from backend.detect.scan import ScanResult, run_scan
from backend.models import Ghost, Question, Series, Transaction


def snapshot() -> dict[str, Any]:
    r = run_scan()
    return {
        "today": r.today.isoformat(), "currency": r.currency,
        "series": [s.model_dump(mode="json") for s in r.series],
        "ghosts": [g.model_dump(mode="json") for g in r.ghosts],
        "questions": [q.model_dump(mode="json") for q in r.questions],
        "upcoming": [u | {"date": u["date"].isoformat()} for u in r.upcoming],
        "pending": r.pending_enrich,
        "transactions": [t.model_dump(mode="json") for t in db.load_transactions()],
    }


def context_from(snap: dict[str, Any]) -> Context:
    scan = ScanResult(
        today=date.fromisoformat(snap["today"]), currency=snap["currency"],
        series=[Series.model_validate(s) for s in snap["series"]],
        ghosts=[Ghost.model_validate(g) for g in snap["ghosts"]],
        questions=[Question.model_validate(q) for q in snap["questions"]],
        upcoming=[u | {"date": date.fromisoformat(u["date"])} for u in snap["upcoming"]],
        pending_enrich=snap["pending"])
    return Context(scan, [Transaction.model_validate(t) for t in snap["transactions"]])
