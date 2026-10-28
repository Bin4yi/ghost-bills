"""Check that Gemma invented nothing before its words are shown.

1. Every money amount and date in the text must appear in the facts.
2. No URLs, phone numbers or email addresses at all.
3. display_name must share a word with the merchant key.
4. Word limits.
"""

from __future__ import annotations

import re
from typing import Any

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_MON = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"

LIMITS = {"story": 20, "epitaph": 12, "explain": 60, "email_body": 120}

_MONEY = re.compile(
    r"(?:[$€£]|\b(?:usd|eur|gbp|lkr|inr|aud|cad|rs\.?)\s?)\s?(\d[\d,]*(?:\.\d{1,2})?)"
    r"|\b(\d[\d,]*\.\d{2})\b", re.I)
_DATE_DMY = re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?{_MON}(?:,?\s+(\d{{4}}))?", re.I)
_DATE_MDY = re.compile(rf"\b{_MON}\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?:,?\s+(\d{{4}}))?", re.I)
_DATE_MY = re.compile(rf"\b{_MON}\s+(\d{{4}})\b", re.I)
_DATE_NUM = re.compile(r"\b\d{1,4}[/.-]\d{1,2}[/.-]\d{2,4}\b")
_URL = re.compile(r"https?://|www\.|\b[\w-]+\.(?:com|net|org|io|co|app|ai|dev|me|uk|lk|ly)\b", re.I)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"\+?\(?\d[\d\s().-]{7,}\d")


def _cents(raw: str) -> int:
    whole, _, frac = raw.replace(",", "").partition(".")
    return int(whole or 0) * 100 + int((frac + "00")[:2])


def amounts_in(text: str) -> set[int]:
    return {_cents(a or b) for a, b in _MONEY.findall(text)}


def dates_in(text: str) -> set[tuple[int | None, int, int | None]]:
    """(day, month, year) with None for parts not written."""
    found: set[tuple[int | None, int, int | None]] = set()
    for d, mon, y in _DATE_DMY.findall(text):
        found.add((int(d), MONTHS[mon.lower()[:3]], int(y) if y else None))
    for mon, d, y in _DATE_MDY.findall(text):
        if len(d) <= 2:
            found.add((int(d), MONTHS[mon.lower()[:3]], int(y) if y else None))
    for mon, y in _DATE_MY.findall(text):
        found.add((None, MONTHS[mon.lower()[:3]], int(y)))
    return found


def _date_ok(d: tuple[int | None, int, int | None], facts: set) -> bool:
    day, mon, year = d
    return any(mon == fm and (day is None or fd is None or day == fd)
               and (year is None or fy is None or year == fy) for fd, fm, fy in facts)


def words(text: str) -> int:
    return len(text.split())


def _phone_like(text: str) -> bool:
    for m in _PHONE.findall(text):
        if sum(c.isdigit() for c in m) >= 9 and not re.fullmatch(r"[\d,]+\.\d{2}", m.strip()):
            return True
    return False


def _shares_word(name: str, keys: list[str]) -> bool:
    key_words = {w.lower() for k in keys for w in re.findall(r"[A-Za-z0-9]+", k)}
    for w in re.findall(r"[A-Za-z0-9]+", name.lower()):
        if w in key_words or (len(w) >= 4 and any(w in kw or kw in w for kw in key_words if len(kw) >= 4)):
            return True
    return False


def check(out: dict[str, Any], facts: list[str], merchant_keys: list[str]) -> list[str]:
    """Return the reasons the output is rejected. Empty list = safe to show."""
    reasons: list[str] = []
    email = out.get("cancel_email") or {}
    texts = {
        "story": out.get("story", ""), "epitaph": out.get("epitaph", ""),
        "explain": out.get("explain", ""),
        "email_subject": email.get("subject", ""), "email_body": email.get("body", ""),
    }
    fact_text = "\n".join(facts)
    fact_amounts = amounts_in(fact_text)
    fact_dates = dates_in(fact_text)
    for field, text in texts.items():
        if not text.strip():
            reasons.append(f"{field} is empty")
            continue
        for a in amounts_in(text) - fact_amounts:
            reasons.append(f"{field} has an amount that is not in the facts: {a / 100:.2f}")
        for d in dates_in(text):
            if not _date_ok(d, fact_dates):
                reasons.append(f"{field} has a date that is not in the facts")
        if _DATE_NUM.search(text):
            reasons.append(f"{field} has a number date; write dates like the facts do")
        clean = text.replace("[YOUR ACCOUNT EMAIL]", "").replace("[YOUR NAME]", "")
        if _URL.search(clean):
            reasons.append(f"{field} has a link; links are not allowed")
        if _EMAIL.search(clean):
            reasons.append(f"{field} has an email address; not allowed")
        if _phone_like(clean):
            reasons.append(f"{field} has a phone number; not allowed")
    for field, limit in LIMITS.items():
        if words(texts[field]) > limit:
            reasons.append(f"{field} is too long ({words(texts[field])} words, max {limit})")
    body = texts["email_body"]
    if "[YOUR NAME]" not in body or "[YOUR ACCOUNT EMAIL]" not in body:
        reasons.append("email body must contain [YOUR NAME] and [YOUR ACCOUNT EMAIL]")
    if not _shares_word(out.get("display_name", ""), merchant_keys):
        reasons.append("display_name must share a word with the merchant name")
    return reasons
