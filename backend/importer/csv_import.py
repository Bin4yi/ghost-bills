"""Read a bank CSV in (almost) any shape. No bank login, no bank API.

Steps: decode -> find delimiter -> skip title rows -> guess columns ->
parse dates (decide day/month order from all rows) -> parse amounts with
Decimal -> keep money going out only.
"""

from __future__ import annotations

import csv
import io
import re
from collections import Counter
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from backend.models import ColumnMapping, Transaction
from backend.normalize import merchant_key

DATE_WORDS = ("date", "posted", "posting", "transaction date", "booking")
DESC_WORDS = ("description", "details", "narrative", "merchant", "payee", "memo",
              "particulars", "reference", "name")
AMOUNT_WORDS = ("amount", "value", "sum")
DEBIT_WORDS = ("debit", "withdrawal", "money out", "paid out", "out")
CREDIT_WORDS = ("credit", "deposit", "money in", "paid in", "in")
CURRENCY_WORDS = ("currency", "ccy")
ORIG_AMOUNT_WORDS = ("original amount", "foreign amount", "orig amount", "amount in original")
ORIG_CURRENCY_WORDS = ("original currency", "foreign currency", "orig currency")

CURRENCY_CODES = ("USD", "EUR", "GBP", "LKR", "INR", "AUD", "CAD", "JPY", "SGD",
                  "CHF", "NZD", "AED", "SEK", "NOK", "DKK")
SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP", "₹": "INR", "¥": "JPY"}
_ORIG_IN_TEXT = re.compile(
    r"\b(" + "|".join(CURRENCY_CODES) + r")\s?(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)\b")

_NUMERIC_DATE = re.compile(r"^\s*(\d{1,4})[/.\-](\d{1,2})[/.\-](\d{1,4})\s*$")
TEXT_DATE_FORMATS = ("%d %b %Y", "%d %B %Y", "%b %d, %Y", "%d-%b-%Y", "%d-%b-%y")


class ImportError_(ValueError):
    """A file we cannot read. The message is shown to the user."""


# --- reading the table ----------------------------------------------------

def decode(data: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ImportError_("Could not read the file as text.")


def sniff_delimiter(text: str) -> str:
    lines = [ln for ln in text.splitlines() if ln.strip()][:30]
    best, best_score = ",", -1
    for d in (",", ";", "\t", "|"):
        counts = [ln.count(d) for ln in lines if ln.count(d) > 0]
        if not counts:
            continue
        common, freq = Counter(counts).most_common(1)[0]
        score = freq * 10 + common
        if score > best_score:
            best, best_score = d, score
    return best


def read_table(text: str) -> tuple[list[str], list[list[str]]]:
    """Return (header, data rows). Skips empty and title rows at the top."""
    delim = sniff_delimiter(text)
    rows = [r for r in csv.reader(io.StringIO(text), delimiter=delim)]
    rows = [[c.strip() for c in r] for r in rows if any(c.strip() for c in r)]
    if not rows:
        raise ImportError_("The file is empty.")
    width = Counter(len(r) for r in rows if len(r) >= 2).most_common(1)
    if not width:
        raise ImportError_("Could not find a table in the file.")
    width = width[0][0]
    for i, row in enumerate(rows):
        if len(row) == width and _looks_like_header(row):
            data = [r + [""] * (width - len(r)) for r in rows[i + 1:] if len(r) >= width - 1]
            return row, [r[:width] for r in data]
    raise ImportError_("Could not find the header row (Date, Description, Amount...).")


def _looks_like_header(row: list[str]) -> bool:
    cells = [c.lower() for c in row]
    has_date = any(any(w in c for w in DATE_WORDS) for c in cells)
    numeric = sum(1 for c in row if _parse_decimal(c) is not None)
    return has_date and numeric == 0


def header_signature(header: list[str]) -> str:
    return "|".join(h.strip().lower() for h in header)


# --- guessing columns -----------------------------------------------------

def _find(header: list[str], words: tuple[str, ...], exclude: set[int],
          exact: bool = False) -> int | None:
    low = [h.lower().strip() for h in header]
    for w in words:  # word order = priority
        for i, h in enumerate(low):
            if i in exclude:
                continue
            if (h == w) if exact else (w in h):
                return i
    return None


def guess_mapping(header: list[str], rows: list[list[str]]) -> ColumnMapping | None:
    used: set[int] = set()
    orig_amount = _find(header, ORIG_AMOUNT_WORDS, used)
    if orig_amount is not None:
        used.add(orig_amount)
    orig_ccy = _find(header, ORIG_CURRENCY_WORDS, used)
    if orig_ccy is not None:
        used.add(orig_ccy)
    d = _find(header, DATE_WORDS, used)
    if d is None:
        return None
    used.add(d)
    desc = _find(header, DESC_WORDS, used)
    if desc is None:
        return None
    used.add(desc)
    debit = _find(header, DEBIT_WORDS[:4], used)
    credit = _find(header, CREDIT_WORDS[:4], used | ({debit} if debit is not None else set()))
    amount = None
    if debit is None:
        amount = _find(header, AMOUNT_WORDS, used)
        if amount is None:
            return None
    else:
        used.add(debit)
    ccy = _find(header, CURRENCY_WORDS, used)
    m = ColumnMapping(date=d, description=desc, amount=amount, debit=debit, credit=credit,
                      currency=ccy, original_amount=orig_amount, original_currency=orig_ccy)
    m.date_order = detect_date_order([r[d] for r in rows])
    m.default_currency = _guess_currency(header, rows, m)
    return m


def _guess_currency(header: list[str], rows: list[list[str]], m: ColumnMapping) -> str:
    for code in CURRENCY_CODES:
        if any(code.lower() in h.lower() for h in header):
            return code
    col = m.amount if m.amount is not None else m.debit
    for r in rows[:50]:
        if col is not None and col < len(r):
            for sym, code in SYMBOLS.items():
                if sym in r[col]:
                    return code
            if "Rs" in r[col]:
                return "LKR"
    return "USD"


# --- dates ----------------------------------------------------------------

def detect_date_order(values: list[str]) -> str | None:
    """'ymd', 'dmy' or 'mdy'. None means: ask the user (needs_user)."""
    parts = [_NUMERIC_DATE.match(v) for v in values if v.strip()]
    nums = [(int(m[1]), int(m[2]), int(m[3])) for m in parts if m]
    if not nums:
        return "dmy"  # text dates like "3 Aug 2026" do not need an order
    if all(len(str(a)) == 4 or a > 31 for a, _, _ in nums):
        return "ymd"
    if any(a > 12 for a, _, _ in nums):
        return "dmy"
    if any(b > 12 for _, b, _ in nums):
        return "mdy"
    return None


def parse_date(value: str, order: str) -> date:
    m = _NUMERIC_DATE.match(value)
    if m:
        a, b, c = int(m[1]), int(m[2]), int(m[3])
        if order == "ymd":
            y, mo, d = a, b, c
        elif order == "dmy":
            d, mo, y = a, b, c
        else:
            mo, d, y = a, b, c
        if y < 100:
            y += 2000
        return date(y, mo, d)
    for fmt in TEXT_DATE_FORMATS:
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    raise ImportError_(f"Could not read the date '{value}'.")


# --- amounts --------------------------------------------------------------

def _parse_decimal(raw: str) -> Decimal | None:
    s = raw.strip()
    if not s:
        return None
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative, s = True, s[1:-1]
    s = s.replace(" ", "").replace(" ", "")
    for code in CURRENCY_CODES:
        s = s.replace(code, "")
    for sym in (*SYMBOLS, "Rs.", "Rs"):
        s = s.replace(sym, "")
    if s.endswith("-"):
        negative, s = True, s[:-1]
    if s.startswith("-"):
        negative, s = not negative, s[1:]
    elif s.startswith("+"):
        s = s[1:]
    if not re.fullmatch(r"[\d.,']+", s or "x"):
        return None
    s = s.replace("'", "")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):  # 1.234,56
            s = s.replace(".", "").replace(",", ".")
        else:  # 1,234.56
            s = s.replace(",", "")
    elif "," in s:
        head, _, tail = s.rpartition(",")
        s = f"{head.replace(',', '')}.{tail}" if len(tail) in (1, 2) else s.replace(",", "")
    try:
        value = Decimal(s)
    except InvalidOperation:
        return None
    return -value if negative else value


def parse_amount(raw: str) -> Decimal | None:
    """Public parser: '$1,234.50' -> Decimal('1234.50'); '(12.00)' -> Decimal('-12.00')."""
    return _parse_decimal(raw)


def to_cents(value: Decimal) -> int:
    return int((value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def original_from_text(description: str) -> tuple[int, str] | None:
    """'LUMENLY READER EUR 4.99' -> (499, 'EUR')."""
    m = _ORIG_IN_TEXT.search(description.upper())
    if not m:
        return None
    value = _parse_decimal(m[2])
    return (to_cents(abs(value)), m[1]) if value is not None else None


# --- building transactions ---------------------------------------------

def build_transactions(rows: list[list[str]], m: ColumnMapping,
                       date_order: str | None = None) -> list[Transaction]:
    order = date_order or m.date_order or "dmy"
    out_is_negative = _out_is_negative(rows, m)
    txs: list[Transaction] = []
    for r in rows:
        desc = r[m.description]
        if not r[m.date].strip() or not desc:
            continue
        out = _money_out(r, m, out_is_negative)
        if out is None:
            continue
        currency = (r[m.currency].strip().upper() if m.currency is not None and r[m.currency].strip()
                    else m.default_currency)
        orig_cents, orig_ccy = _original(r, m, desc)
        if orig_ccy == currency:
            orig_cents, orig_ccy = None, None
        txs.append(Transaction(
            date=parse_date(r[m.date], order), description_raw=desc,
            merchant_key=merchant_key(desc), amount_cents=to_cents(out), currency=currency,
            original_amount_cents=orig_cents, original_currency=orig_ccy))
    txs.sort(key=lambda t: t.date)
    return txs


def _out_is_negative(rows: list[list[str]], m: ColumnMapping) -> bool:
    if m.amount is None:
        return False
    values = [_parse_decimal(r[m.amount]) for r in rows]
    return any(v is not None and v < 0 for v in values)


def _money_out(r: list[str], m: ColumnMapping, out_is_negative: bool) -> Decimal | None:
    """Positive amount of money going out, or None for money coming in."""
    if m.amount is not None:
        v = _parse_decimal(r[m.amount])
        if v is None:
            return None
        if out_is_negative:
            return -v if v <= 0 else None
        return v if v >= 0 else None
    if m.debit is not None:
        v = _parse_decimal(r[m.debit])
        if v is not None:
            return abs(v)
    return None


def _original(r: list[str], m: ColumnMapping, desc: str) -> tuple[int | None, str | None]:
    if m.original_amount is not None and r[m.original_amount].strip():
        v = _parse_decimal(r[m.original_amount])
        ccy = r[m.original_currency].strip().upper() if m.original_currency is not None else None
        if v is not None and ccy:
            return to_cents(abs(v)), ccy
    found = original_from_text(desc)
    return found if found else (None, None)
