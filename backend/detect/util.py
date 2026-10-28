"""Small date and money helpers. Integer cents only."""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from statistics import median

SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£"}


def add_months(d: date, n: int, day: int | None = None) -> date:
    """Same day n months later; the 31st becomes the last day of short months."""
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    return date(y, m, min(day or d.day, calendar.monthrange(y, m)[1]))


def add_years(d: date, n: int = 1) -> date:
    try:
        return d.replace(year=d.year + n)
    except ValueError:  # 29 Feb -> 28 Feb
        return d.replace(year=d.year + n, day=28)


def next_after(last: date, interval: str, anchor_day: int | None = None) -> date:
    if interval == "weekly":
        return last + timedelta(days=7)
    if interval == "monthly":
        return add_months(last, 1, anchor_day)
    return add_years(last)


def median_int(values: list[int]) -> int:
    return int(round(median(values)))


def money(cents: int, currency: str = "USD") -> str:
    """1299 -> '$12.99'. Always shows the currency."""
    sign = "-" if cents < 0 else ""
    whole, part = divmod(abs(cents), 100)
    number = f"{whole:,}.{part:02d}"
    sym = SYMBOLS.get(currency)
    return f"{sign}{sym}{number}" if sym else f"{sign}{currency} {number}"


def day(d: date) -> str:
    """'3 Aug 2026'."""
    return f"{d.day} {d:%b %Y}"


def month(d: date) -> str:
    """'Aug 2026'."""
    return f"{d:%b %Y}"
