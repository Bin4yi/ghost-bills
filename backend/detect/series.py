"""Step 1: find repeating charges ("series"). Plain Python, no AI."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from backend.detect import config as C
from backend.detect.util import median_int, next_after
from backend.models import Series, Transaction

CATEGORY_MAP: dict[str, str] = json.loads(
    (Path(__file__).parent / "categories.json").read_text(encoding="utf-8"))


@dataclass
class NearMiss:
    """Looks like a subscription but only 50-70% of gaps fit: Penny asks."""
    merchant_key: str
    interval: str
    amount_cents: int
    currency: str
    count: int
    gaps: list[int]
    fitting: int


def group_by_merchant(txs: list[Transaction]) -> dict[str, list[Transaction]]:
    groups: dict[str, list[Transaction]] = defaultdict(list)
    for t in sorted(txs, key=lambda t: t.date):
        groups[t.merchant_key].append(t)
    return groups


def gaps_of(dates: list[date]) -> list[int]:
    return [(b - a).days for a, b in zip(dates, dates[1:])]


def pattern_of(gaps: list[int]) -> tuple[str | None, float]:
    """Interval named by the median gap, and the share of gaps that fit it."""
    if not gaps:
        return None, 0.0
    mid = sorted(gaps)[len(gaps) // 2] if len(gaps) % 2 else median_int(gaps)
    for name, (lo, hi) in C.PATTERNS.items():
        if lo <= mid <= hi:
            fit = sum(1 for g in gaps if lo <= g <= hi)
            return name, fit / len(gaps)
    return None, 0.0


def _within(values: list[int], tol: float) -> bool:
    mid = median_int(values)
    return all(abs(v - mid) <= mid * tol for v in values)


def amounts_stable(amounts: list[int], tol: float = C.AMOUNT_TOLERANCE) -> bool:
    """All near the median, or one clear step up/down that then stays."""
    if _within(amounts, tol):
        return True
    for k in range(1, len(amounts)):
        before, after = amounts[:k], amounts[k:]
        if _within(before, tol) and _within(after, tol):
            return True
    return False


def price_step(amounts: list[int]) -> tuple[int, int, int] | None:
    """(old price, new price, index where the new price starts) or None."""
    if len(amounts) < 2:
        return None
    new = amounts[-1]
    i = len(amounts) - 1
    while i > 0 and abs(amounts[i - 1] - new) <= max(1, new // 100):
        i -= 1
    if i == 0:
        return None
    return median_int(amounts[:i]), new, i


def compare_amounts(charges: list[Transaction]) -> tuple[list[int], str | None]:
    """Use the original foreign amounts when every charge has them in one currency."""
    ccys = {t.original_currency for t in charges}
    if len(ccys) == 1 and None not in ccys and all(t.original_amount_cents for t in charges):
        return [t.original_amount_cents or 0 for t in charges], ccys.pop()
    return [t.amount_cents for t in charges], None


def looks_foreign(charges: list[Transaction]) -> bool:
    if any(t.original_currency for t in charges):
        return True
    words = {w for t in charges for w in t.description_raw.upper().replace("-", " ").split()}
    return any(w in words for w in C.FOREIGN_WORDS)


def is_essential(key: str) -> bool:
    words = key.split()
    return any(w in words for w in C.ESSENTIAL_WORDS)


def category_for(key: str, user: dict[str, tuple[str, str]]) -> tuple[str | None, str | None]:
    """User choice first, then the built-in map, then a Gemma suggestion."""
    if key in user and user[key][1] == "user":
        return user[key][0], "user"
    for word, cat in CATEGORY_MAP.items():
        if word in key:
            return cat, "map"
    if key in user:
        return user[key]
    return None, None


def _anchor_day(dates: list[date]) -> int:
    return Counter(d.day for d in dates).most_common(1)[0][0]


def build_series(key: str, charges: list[Transaction], interval: str, today: date,
                 essential_override: dict[str, bool],
                 categories: dict[str, tuple[str, str]]) -> Series:
    dates = [t.date for t in charges]
    orig, orig_ccy = compare_amounts(charges)
    last = dates[-1]
    nxt = next_after(last, interval, _anchor_day(dates) if interval == "monthly" else None)
    active = (today - last).days <= C.ACTIVE_FACTOR * C.INTERVAL_DAYS[interval]
    cat, src = category_for(key, categories)
    return Series(
        id=key, merchant_key=key, interval=interval,  # type: ignore[arg-type]
        amounts=[t.amount_cents for t in charges],
        original_amounts=orig if orig_ccy else None, original_currency=orig_ccy,
        currency=charges[-1].currency, dates=dates, last_date=last, next_date=nxt,
        active=active, essential=essential_override.get(key, is_essential(key)),
        category=cat, category_source=src,  # type: ignore[arg-type]
        foreign=looks_foreign(charges))


def find_series(txs: list[Transaction], today: date,
                forced: set[str] | None = None,
                rejected: set[str] | None = None,
                essential_override: dict[str, bool] | None = None,
                categories: dict[str, tuple[str, str]] | None = None,
                ) -> tuple[list[Series], list[NearMiss]]:
    """Return (series, near misses). `forced` keys were confirmed by the user."""
    forced, rejected = forced or set(), rejected or set()
    essential_override, categories = essential_override or {}, categories or {}
    found: list[Series] = []
    near: list[NearMiss] = []
    for key, charges in group_by_merchant(txs).items():
        charges = [t for t in charges if t.amount_cents > 0]  # $0 trials are not prices
        if len(charges) < C.MIN_CHARGES_YEARLY:
            continue
        gaps = gaps_of([t.date for t in charges])
        interval, share = pattern_of(gaps)
        amounts, _ = compare_amounts(charges)
        need = C.MIN_CHARGES_YEARLY if interval == "yearly" else C.MIN_CHARGES
        if interval is None or len(charges) < need or not amounts_stable(amounts):
            continue
        is_near = C.QUESTION_SHARE <= share < C.PATTERN_SHARE
        if is_near and not is_essential(key):
            # Kept even after an answer, so the card can show "You said: ...".
            lo, hi = C.PATTERNS[interval]
            near.append(NearMiss(key, interval, median_int(amounts), charges[-1].currency,
                                 len(charges), gaps, sum(1 for g in gaps if lo <= g <= hi)))
        if (share >= C.PATTERN_SHARE or (is_near and key in forced)) and key not in rejected:
            found.append(build_series(key, charges, interval, today,
                                      essential_override, categories))
    found.sort(key=lambda s: s.merchant_key)
    return found, near
