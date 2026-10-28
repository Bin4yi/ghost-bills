"""Step 2: the 4 ghost rules. Every ghost and every amount comes from here."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from backend.detect import config as C
from backend.detect.series import (amounts_stable, compare_amounts, gaps_of,
                                   group_by_merchant, is_essential, pattern_of,
                                   price_step)
from backend.detect.util import day, median_int, money, month, next_after
from backend.models import Ghost, Series, Transaction
from backend.normalize import display_name

FX_NOTE = "price changed, maybe exchange rate"
EVERY = {"weekly": "every week", "monthly": "every month", "yearly": "every year"}


def ghost_id(kind: str, keys: list[str]) -> str:
    return f"{kind}:" + "+".join(sorted(k.lower().replace(" ", "-") for k in keys))


def _candidates(series: list[Series]) -> list[Series]:
    return [s for s in series if s.active and not s.essential]


# --- Poltergeist ----------------------------------------------------------

def poltergeists(series: list[Series]) -> list[Ghost]:
    """Newest price at least 5% and 0.50 above the old stable price.

    Original foreign amounts are compared when the statement has them, so a
    moving exchange rate is never a price rise. A foreign line without them
    needs 15% to be called a ghost; 5-15% becomes a question (waiting)."""
    out = []
    for s in _candidates(series):
        compare = s.original_amounts or s.amounts
        step = price_step(compare)
        if step is None:
            continue
        old, new, start = step
        if not _rise(old, new, C.PRICE_UP_PCT):
            continue
        fx_note, waiting = None, False
        if s.foreign and not s.original_amounts:
            fx_note = FX_NOTE
            waiting = not _rise(old, new, C.FX_PRICE_UP_PCT)
        old_file = median_int(s.amounts[:start])
        diff = max(s.amounts[-1] - old_file, 0)
        yearly = diff * s.per_year
        ccy = s.original_currency or s.currency
        evidence = [
            f"{money(old, ccy)} {EVERY[s.interval]} from {month(s.dates[0])} to {month(s.dates[start - 1])}",
            f"{money(new, ccy)} since {day(s.dates[start])}",
            f"{money(diff, s.currency)} more each time, {money(yearly, s.currency)} more per year",
        ]
        if fx_note:
            evidence.append("Charged in a foreign currency; the statement has no original amount")
        out.append(Ghost(
            id=ghost_id("poltergeist", [s.merchant_key]), type="poltergeist",
            series_ids=[s.id], merchant_keys=[s.merchant_key], evidence=evidence,
            yearly_cents=yearly, currency=s.currency, next_date=s.next_date,
            next_amount_cents=s.amounts[-1], display_name=display_name(s.merchant_key),
            fx_note=fx_note, waiting=waiting))
    return out


def _rise(old: int, new: int, pct: float) -> bool:
    return new - old >= C.PRICE_UP_MIN_CENTS and new * 100 >= old * round(100 * (1 + pct))


# --- Sleepy Ghost -----------------------------------------------------------

def sleepy_ghosts(series: list[Series], today: date) -> list[Ghost]:
    """Yearly plan whose next charge is within RENEW_SOON_DAYS."""
    out = []
    for s in _candidates(series):
        days_left = (s.next_date - today).days
        if s.interval != "yearly" or not 0 <= days_left <= C.RENEW_SOON_DAYS:
            continue
        price = s.amounts[-1]
        past = " and ".join(day(d) for d in s.dates[-2:])
        evidence = [
            f"{money(price, s.currency)} charged on {past}",
            f"Next charge expected on {day(s.next_date)}, in {days_left} days",
            f"{money(price, s.currency)} per year",
        ]
        out.append(Ghost(
            id=ghost_id("sleepy", [s.merchant_key]), type="sleepy", series_ids=[s.id],
            merchant_keys=[s.merchant_key], evidence=evidence, yearly_cents=price,
            currency=s.currency, next_date=s.next_date, next_amount_cents=price,
            display_name=display_name(s.merchant_key)))
    return out


# --- Shapeshifter -----------------------------------------------------------

def shapeshifters(txs: list[Transaction], today: date) -> list[Ghost]:
    """Own scan: the first charge from a merchant is a tiny 'trial' in the last
    90 days, then at least 2 charges at full price."""
    out = []
    for key, charges in group_by_merchant(txs).items():
        if len(charges) < 3 or is_essential(key):
            continue
        trial, later = charges[0], charges[1:]
        if (today - trial.date).days > C.TRIAL_WINDOW_DAYS:
            continue
        amounts, _ = compare_amounts(later)
        full = median_int([t.amount_cents for t in later])
        if full <= C.TRIAL_MAX_CENTS or not amounts_stable(amounts) or \
                any(abs(t.amount_cents - full) > full * C.AMOUNT_TOLERANCE for t in later):
            continue
        if not (trial.amount_cents <= C.TRIAL_MAX_CENTS
                or trial.amount_cents <= full * C.TRIAL_SHARE):
            continue
        interval, _ = pattern_of(gaps_of([t.date for t in later]))
        interval = interval or "monthly"
        per_year = C.PER_YEAR[interval]
        ccy = later[-1].currency
        dates = " and ".join(day(t.date) for t in later[-2:])
        evidence = [
            f"{money(trial.amount_cents, ccy)} on {day(trial.date)} (the trial)",
            f"{money(full, ccy)} on {dates}",
            f"{money(full * per_year, ccy)} per year at this price",
        ]
        out.append(Ghost(
            id=ghost_id("shapeshifter", [key]), type="shapeshifter", series_ids=[],
            merchant_keys=[key], evidence=evidence, yearly_cents=full * per_year,
            currency=ccy, next_date=next_after(later[-1].date, interval, later[-1].date.day),
            next_amount_cents=full, display_name=display_name(key)))
    return out


# --- Twin Ghosts -------------------------------------------------------------

def twin_ghosts(series: list[Series]) -> list[Ghost]:
    """Two active series in the same confirmed category (map or user, never a guess)."""
    by_cat: dict[str, list[Series]] = defaultdict(list)
    for s in _candidates(series):
        if s.category and s.category_source in ("map", "user"):
            by_cat[s.category].append(s)
    out = []
    for cat, group in sorted(by_cat.items()):
        if len(group) < 2:
            continue
        group.sort(key=lambda s: s.yearly_cents, reverse=True)
        cheaper = group[-1]
        evidence = [f"{display_name(s.merchant_key)}: {money(s.price_cents, s.currency)} "
                    f"{EVERY[s.interval]}" for s in group[:3]]
        evidence.append(f"All are in the {cat} category")
        evidence.append(f"Cancel the cheaper one to save {money(cheaper.yearly_cents, cheaper.currency)} per year")
        out.append(Ghost(
            id=ghost_id("twins", [s.merchant_key for s in group]), type="twins",
            series_ids=[s.id for s in group], merchant_keys=[s.merchant_key for s in group],
            evidence=evidence[:4] if len(evidence) > 4 else evidence,
            yearly_cents=cheaper.yearly_cents, currency=cheaper.currency,
            next_date=min(s.next_date for s in group),
            next_amount_cents=cheaper.price_cents,
            display_name=" & ".join(display_name(s.merchant_key) for s in group[:3])))
    return out


def all_ghosts(series: list[Series], txs: list[Transaction], today: date) -> list[Ghost]:
    ghosts = (poltergeists(series) + sleepy_ghosts(series, today)
              + shapeshifters(txs, today) + twin_ghosts(series))
    ghosts.sort(key=lambda g: (-g.yearly_cents, g.id))
    return ghosts
