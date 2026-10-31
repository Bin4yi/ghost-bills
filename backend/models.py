"""Data shapes shared by the importer, detection, LLM and API."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Interval = Literal["weekly", "monthly", "yearly"]
GhostType = Literal["poltergeist", "sleepy", "shapeshifter", "twins"]
CategorySource = Literal["map", "user", "suggested"]


class Transaction(BaseModel):
    id: int | None = None
    date: date
    description_raw: str
    merchant_key: str
    amount_cents: int  # money out, always >= 0
    currency: str = "USD"
    original_amount_cents: int | None = None
    original_currency: str | None = None


class Series(BaseModel):
    id: str  # the merchant key, stable across scans
    merchant_key: str
    interval: Interval
    amounts: list[int]
    original_amounts: list[int] | None = None
    original_currency: str | None = None
    currency: str = "USD"
    dates: list[date]
    last_date: date
    next_date: date
    active: bool
    essential: bool = False
    category: str | None = None
    category_source: CategorySource | None = None
    foreign: bool = False

    @property
    def price_cents(self) -> int:
        return self.amounts[-1]

    @property
    def per_year(self) -> int:
        return {"weekly": 52, "monthly": 12, "yearly": 1}[self.interval]

    @property
    def yearly_cents(self) -> int:
        return self.price_cents * self.per_year


class CancelEmail(BaseModel):
    subject: str
    body: str


class Ghost(BaseModel):
    id: str
    type: GhostType
    series_ids: list[str]
    merchant_keys: list[str]
    evidence: list[str]
    yearly_cents: int
    currency: str = "USD"
    next_date: date | None = None
    next_amount_cents: int | None = None
    display_name: str
    story: str | None = None
    epitaph: str | None = None
    explain: str | None = None
    cancel_email: CancelEmail | None = None
    fx_note: str | None = None
    waiting: bool = False  # depends on an open question
    status: Literal["active", "kept", "cancelled", "cancel_requested"] = "active"
    cancelled_at: date | None = None
    text_source: Literal["gemma", "template"] | None = None


class Question(BaseModel):
    id: str
    kind: Literal["subscription", "date_order", "fx"]
    ref_id: str
    tag: str
    question: str
    why: str
    choice_a: str
    choice_b: str
    answer: Literal["a", "b"] | None = None


class ColumnMapping(BaseModel):
    """Column indexes for one bank's CSV shape."""
    date: int
    description: int
    amount: int | None = None
    debit: int | None = None
    credit: int | None = None
    currency: int | None = None
    original_amount: int | None = None
    original_currency: int | None = None
    date_order: Literal["ymd", "dmy", "mdy"] | None = None
    default_currency: str = "USD"


class ImportPreview(BaseModel):
    upload_id: str
    signature: str
    headers: list[str]
    rows: list[list[str]] = Field(default_factory=list)
    mapping: ColumnMapping | None
    needs_user: bool = False
    from_profile: bool = False
    message: str | None = None
