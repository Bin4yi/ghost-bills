"""Read-only tools for "Ask Penny". All math happens here, in Python, in cents.

No tool can send email, open links or change data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Callable

from backend.detect.scan import ScanResult
from backend.detect.util import day, money
from backend.models import Series, Transaction
from backend.normalize import display_name


@dataclass
class Context:
    scan: ScanResult
    txs: list[Transaction]
    # Set only when you're logged in: hands a send job to Courier. Penny never sends.
    handoff: Callable[[str], dict[str, Any]] | None = None

    @property
    def today(self) -> date:
        return self.scan.today

    @property
    def ccy(self) -> str:
        return self.scan.currency


def find_key(ctx: Context, name: str | None) -> str | None:
    """Match what the user typed ('cloudcrate', 'Moonbeam') to a merchant key."""
    if not name:
        return None
    want = name.upper().strip()
    keys = sorted({t.merchant_key for t in ctx.txs})
    for test in (lambda k: k == want, lambda k: k.startswith(want), lambda k: want in k,
                 lambda k: want.replace(" ", "") in k.replace(" ", "")):
        hits = [k for k in keys if test(k)]
        if hits:
            return hits[0]
    words = {w for w in want.split() if len(w) >= 4}
    hits = [k for k in keys if words & set(k.split())]
    return hits[0] if hits else None


def _series_line(s: Series) -> str:
    every = {"weekly": "every week", "monthly": "every month", "yearly": "every year"}[s.interval]
    cat = f", {s.category}" if s.category else ""
    return (f"{display_name(s.merchant_key)}{cat}: {money(s.price_cents, s.currency)} {every}, "
            f"{money(s.yearly_cents, s.currency)} per year, next charge {day(s.next_date)}")


def list_subscriptions(ctx: Context, category: str | None = None) -> dict[str, Any]:
    subs = [s for s in ctx.scan.series if s.active and not s.essential]
    if category:
        subs = [s for s in subs if (s.category or "").lower() == category.lower().strip()]
    total = sum(s.yearly_cents for s in subs)
    lines = [_series_line(s) for s in subs]
    label = f"{category} subscriptions" if category else "subscriptions"
    lines.append(f"Total for {len(subs)} {label}: {money(total, ctx.ccy)} per year")
    return {"count": len(subs), "total_yearly_cents": total, "summary": lines}


def list_ghosts(ctx: Context, type: str | None = None) -> dict[str, Any]:
    ghosts = [g for g in ctx.scan.ghosts if g.status == "active"]
    if type:
        ghosts = [g for g in ghosts if g.type == type.lower().strip()]
    lines = []
    for i, g in enumerate(ghosts, 1):
        nxt = f", next charge {day(g.next_date)}" if g.next_date else ""
        wait = " (waiting for your answer)" if g.waiting else ""
        lines.append(f"{i}. {g.display_name} ({g.type}): {money(g.yearly_cents, g.currency)} "
                     f"per year{nxt}{wait}")
    total = sum(g.yearly_cents for g in ghosts if not g.waiting)
    lines.append(f"Biggest first. Together: {money(total, ctx.ccy)} per year")
    return {"count": len(ghosts), "total_yearly_cents": total, "summary": lines}


def get_charges(ctx: Context, merchant_key: str | None = None, months: int = 12) -> dict[str, Any]:
    key = find_key(ctx, merchant_key)
    if key is None:
        return {"error": f"No charges found for '{merchant_key}'.", "summary": [
            f"No charges found for that name."]}
    since = ctx.today - timedelta(days=int(months) * 31)
    charges = [t for t in ctx.txs if t.merchant_key == key and t.date >= since]
    total = sum(t.amount_cents for t in charges)
    lines = [f"{day(t.date)}: {money(t.amount_cents, t.currency)}" for t in charges[-12:]]
    lines.append(f"{len(charges)} charges from {display_name(key)} in the last {months} months, "
                 f"total {money(total, ctx.ccy)}")
    s = next((s for s in ctx.scan.series if s.merchant_key == key), None)
    if s is not None:
        lines.append(f"Next charge expected on {day(s.next_date)}: {money(s.price_cents, s.currency)}")
    return {"merchant": key, "count": len(charges), "total_cents": total, "summary": lines}


def total_spend(ctx: Context, category: str | None = None, months: int = 12) -> dict[str, Any]:
    since = ctx.today - timedelta(days=int(months) * 31)
    if category:
        keys = {s.merchant_key for s in ctx.scan.series
                if (s.category or "").lower() == category.lower().strip()}
    else:
        keys = {t.merchant_key for t in ctx.txs}
    charges = [t for t in ctx.txs if t.merchant_key in keys and t.date >= since]
    total = sum(t.amount_cents for t in charges)
    what = f"on {category}" if category else "in total"
    return {"total_cents": total, "summary": [
        f"You spent {money(total, ctx.ccy)} {what} in the last {months} months "
        f"({len(charges)} charges)"]}


def compare(ctx: Context, merchant_a: str | None = None,
            merchant_b: str | None = None) -> dict[str, Any]:
    lines = []
    for name in (merchant_a, merchant_b):
        key = find_key(ctx, name)
        s = next((s for s in ctx.scan.series if s.merchant_key == key), None)
        if s is None:
            lines.append(f"{name}: not a subscription I found")
        else:
            lines.append(_series_line(s) + f", last charge {day(s.last_date)}")
    return {"summary": lines}


def request_send(ctx: Context, ghost_id: str | None = None) -> dict[str, Any]:
    """Ask Courier to send a ghost's cancel email. Penny can't send, choose the address,
    or approve: Courier checks your request, and your phone must approve."""
    if ctx.handoff is None:
        return {"summary": ["I can't send emails here. Log in, then use 'Send with Gmail' "
                            "on the ghost you want to cancel."]}
    if not ghost_id:
        return {"summary": ["Tell me which ghost, and I'll ask Courier."]}
    return ctx.handoff(ghost_id)


TOOLS: dict[str, Callable[..., dict[str, Any]]] = {
    "list_subscriptions": list_subscriptions,
    "list_ghosts": list_ghosts,
    "get_charges": get_charges,
    "total_spend": total_spend,
    "compare": compare,
    "request_send": request_send,
}

ARG_NAMES = {
    "list_subscriptions": ("category",),
    "list_ghosts": ("type",),
    "get_charges": ("merchant_key", "months"),
    "total_spend": ("category", "months"),
    "compare": ("merchant_a", "merchant_b"),
    "request_send": ("ghost_id",),  # never an address: only the user types that
}

TOOL_HELP = """\
- list_subscriptions(category?): active subscriptions with price, yearly cost, next charge, and the yearly total.
- list_ghosts(type?): ghosts (poltergeist, sleepy, shapeshifter, twins), biggest money per year first.
- get_charges(merchant_key, months?): past charges of one merchant and the next expected charge.
- total_spend(category?, months?): money actually spent in the last N months.
- compare(merchant_a, merchant_b): two subscriptions side by side.
- request_send(ghost_id): ask Courier to send that ghost's cancel email. Only works if the
  user already pressed 'Send with Gmail' for it, and the user must approve on their phone."""


def fill_category(ctx: Context, name: str, args: dict[str, Any], question: str) -> dict[str, Any]:
    """Small models often drop the category ("how much on music?" -> no category).
    If the question names a category we know, code fills it in."""
    if name not in ("list_subscriptions", "total_spend") or args.get("category"):
        return args
    words = {w.strip("?.,!").lower() for w in question.split()}
    known = sorted({s.category for s in ctx.scan.series if s.category})
    hit = next((c for c in known if c in words), None)
    return {**args, "category": hit} if hit else args


def run(ctx: Context, name: str, args: dict[str, Any]) -> dict[str, Any]:
    fn = TOOLS[name]
    clean = {k: v for k, v in (args or {}).items()
             if k in ARG_NAMES[name] and v not in (None, "", 0)}
    if "months" in clean:
        try:
            clean["months"] = max(1, min(36, int(clean["months"])))
        except (TypeError, ValueError):
            clean.pop("months")
    return fn(ctx, **clean)
