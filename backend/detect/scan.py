"""Run the whole detector on the stored statement and apply the user's answers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta

from backend import db, settings
from backend.detect import config as C
from backend.detect import questions as Q
from backend.detect.rules import all_ghosts
from backend.detect.series import find_series
from backend.importer import csv_import
from backend.llm import enrich
from backend.models import Ghost, Question, Series, Transaction
from backend.normalize import display_name


@dataclass
class ScanResult:
    today: date
    currency: str
    series: list[Series]
    ghosts: list[Ghost]
    questions: list[Question]
    upcoming: list[dict] = field(default_factory=list)
    pending_enrich: int = 0

    @property
    def counted(self) -> list[Ghost]:
        return [g for g in self.ghosts if not g.waiting and g.status == "active"]

    def totals(self) -> dict[str, int]:
        shapeshift_extra = sum(g.yearly_cents for g in self.ghosts
                               if g.type == "shapeshifter" and not g.series_ids)
        subs = sum(s.yearly_cents for s in self.series if s.active and not s.essential)
        return {
            "total_ghost_yearly_cents": sum(g.yearly_cents for g in self.counted),
            "total_subscriptions_yearly_cents": subs + shapeshift_extra,
            "saved_yearly_cents": sum(g.yearly_cents for g in self.ghosts
                                      if g.status == "cancelled"),
        }


def _answers() -> dict[str, str]:
    return {r["question_id"]: r["answer"] for r in db.all_rows("answers")}


def _categories() -> dict[str, tuple[str, str]]:
    return {r["merchant_key"]: (r["category"], r["source"]) for r in db.all_rows("categories")}


def _essentials() -> dict[str, bool]:
    return {r["merchant_key"]: bool(r["essential"]) for r in db.all_rows("essentials")}


def _statuses() -> dict[str, dict]:
    return {r["ghost_id"]: r for r in db.all_rows("ghost_status")}


def run_scan(txs: list[Transaction] | None = None, today: date | None = None) -> ScanResult:
    txs = db.load_transactions() if txs is None else txs
    today = today or settings.today()
    answers = _answers()
    forced = {qid.split(":", 1)[1] for qid, a in answers.items()
              if qid.startswith("subscription:") and a == "a"}
    series, near = find_series(txs, today, forced=forced, essential_override=_essentials(),
                               categories=_categories())
    questions = [Q.subscription_question(n) for n in near]
    questions += _date_questions()

    ghosts: list[Ghost] = []
    for g in all_ghosts(series, txs, today):
        if g.fx_note:
            q = Q.fx_question(g)
            questions.append(q)
            answer = answers.get(q.id)
            if answer == "b":
                continue  # the user said: just the exchange rate
            g.waiting = g.waiting and answer != "a"
        ghosts.append(g)
    _apply_status(ghosts)
    pending = enrich.apply_cached_or_template(ghosts)
    questions = Q.with_answers(questions, answers)
    currency = txs[-1].currency if txs else "USD"
    return ScanResult(today, currency, series, ghosts, questions,
                      upcoming(series, ghosts, today), pending)


def _date_questions() -> list[Question]:
    last = db.last_import()
    if last is None:
        return []
    qid = f"date_order:{last['signature']}"
    answered = db.get_row("answers", "question_id", qid) is not None
    if not last["needs_user"] and not answered:
        return []
    mapping = json.loads(last["mapping_json"])
    _, rows = csv_import.read_table(last["raw_text"])
    dates = [r[mapping["date"]] for r in rows if r[mapping["date"]].strip()]
    return [Q.date_order_question(last["signature"], dates[0] if dates else "?", len(dates))]


def _apply_status(ghosts: list[Ghost]) -> None:
    statuses = _statuses()
    for g in ghosts:
        row = statuses.get(g.id)
        if row:
            g.status = row["status"]
            g.cancelled_at = date.fromisoformat(row["cancelled_at"]) if row["cancelled_at"] else None


def upcoming(series: list[Series], ghosts: list[Ghost], today: date,
             days: int = C.RENEW_SOON_DAYS) -> list[dict]:
    """Charges expected in the next 30 days (subscriptions + shapeshifters)."""
    end = today + timedelta(days=days)
    ghost_of = {k: g.type for g in ghosts for k in g.merchant_keys if g.type != "twins"}
    items = [{"merchant_key": s.merchant_key, "display_name": display_name(s.merchant_key),
              "date": s.next_date, "amount_cents": s.price_cents, "currency": s.currency,
              "ghost_type": ghost_of.get(s.merchant_key)}
             for s in series if s.active and not s.essential and today <= s.next_date <= end]
    seen = {i["merchant_key"] for i in items}
    for g in ghosts:
        if g.type == "shapeshifter" and g.merchant_keys[0] not in seen and g.next_date \
                and today <= g.next_date <= end:
            items.append({"merchant_key": g.merchant_keys[0], "display_name": g.display_name,
                          "date": g.next_date, "amount_cents": g.next_amount_cents,
                          "currency": g.currency, "ghost_type": "shapeshifter"})
    items.sort(key=lambda i: (i["date"], i["merchant_key"]))
    return items
