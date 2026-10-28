"""Turn messy bank descriptions into a stable merchant key. No AI here.

    "MOONBEAM*MUSIC 8831 LONDON"  ->  "MOONBEAM MUSIC"
"""

from __future__ import annotations

import re

NOISE_WORDS = {
    "POS", "PURCHASE", "RECURRING", "DEBIT", "CREDIT", "CARD", "VISA",
    "MASTERCARD", "PAYMENT", "TXN", "TRX", "REF", "ONLINE", "SUBSCRIPTION",
    "FX", "FOREIGN", "INTL", "INTERNATIONAL", "PMT", "AUTOPAY",
}

# Trailing place names banks add after the merchant. Kept short on purpose.
CITIES = [
    "NEW YORK", "SAN FRANCISCO", "LOS ANGELES", "SAN JOSE", "LONDON", "DUBLIN",
    "AMSTERDAM", "SINGAPORE", "SEATTLE", "CHICAGO", "BOSTON", "TORONTO",
    "SYDNEY", "MELBOURNE", "COLOMBO", "KANDY", "GALLE", "BERLIN", "PARIS",
    "LUXEMBOURG", "MUMBAI", "BANGALORE", "DELHI", "DUBAI", "AUSTIN",
]
COUNTRY_CODES = {"US", "USA", "GB", "UK", "IE", "LK", "NL", "SG", "CA", "AU",
                 "DE", "FR", "LU", "AE", "NY", "WA", "TX"}

_CURRENCY_AMOUNT = re.compile(
    r"\b(?:USD|EUR|GBP|LKR|INR|AUD|CAD|JPY|SGD|CHF|NZD|AED|SEK|NOK|DKK)\s?\d+(?:[.,]\d+)*\b")
_DATE = re.compile(r"\b\d{1,4}[/.-]\d{1,2}(?:[/.-]\d{2,4})?\b")
_MASKED_CARD = re.compile(r"\b[X*]{2,}\d{2,4}\b")
_DIGITS = re.compile(r"\b\w*\d{3,}\w*\b")
_NON_WORD = re.compile(r"[^A-Z0-9& ]+")
_SPACES = re.compile(r"\s+")


def merchant_key(description: str) -> str:
    """Clean a raw description into the key used to group charges."""
    text = description.upper()
    text = _MASKED_CARD.sub(" ", text)
    text = _CURRENCY_AMOUNT.sub(" ", text)
    text = _DATE.sub(" ", text)
    text = re.sub(r"[*#_/\\|:.,]", " ", text)
    text = _DIGITS.sub(" ", text)
    text = _NON_WORD.sub(" ", text)
    words = [w for w in text.split() if w not in NOISE_WORDS and not w.isdigit()]
    text = " ".join(words)
    text = _strip_trailing_place(text)
    text = _SPACES.sub(" ", text).strip()
    return text or description.strip().upper()


def _strip_trailing_place(text: str) -> str:
    changed = True
    while changed and text:
        changed = False
        words = text.split()
        if len(words) > 1 and words[-1] in COUNTRY_CODES:
            text = " ".join(words[:-1])
            changed = True
            continue
        for city in CITIES:
            if text.endswith(" " + city):
                text = text[: -len(city) - 1]
                changed = True
                break
    return text


def display_name(key: str) -> str:
    """Plain fallback name before Gemma makes a nicer one."""
    return " ".join(w.capitalize() for w in key.split())
