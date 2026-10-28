from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from backend import seed_demo
from backend.app import app
from backend.detect import rules
from backend.detect.scan import run_scan
from backend.detect.series import amounts_stable, find_series, pattern_of, price_step
from backend.detect.util import add_months, money, next_after
from backend.models import Transaction
from backend.normalize import merchant_key

TODAY = date(2026, 10, 27)


def tx(d: date, desc: str, cents: int, orig: int | None = None, ccy: str | None = None) -> Transaction:
    return Transaction(date=d, description_raw=desc, merchant_key=merchant_key(desc),
                       amount_cents=cents, original_amount_cents=orig, original_currency=ccy)


def monthly(desc: str, start: date, amounts: list[int]) -> list[Transaction]:
    return [tx(add_months(start, i), desc, a) for i, a in enumerate(amounts)]


# --- demo data: the 4 planted ghosts ----------------------------------------

@pytest.fixture
def demo(tmp_path):
    seed_demo.seed(tmp_path / "demo.csv", reset=False)
    return run_scan(today=TODAY)


def test_demo_has_exactly_four_ghosts(demo) -> None:
    counted = {(g.type, tuple(g.merchant_keys), g.yearly_cents) for g in demo.counted}
    assert counted == {
        ("poltergeist", ("MOONBEAM MUSIC",), 3600),
        ("sleepy", ("CLOUDCRATE",), 11900),
        ("shapeshifter", ("PIXELPAL PRO",), 17988),
        ("twins", ("MOONBEAM MUSIC", "ECHOTUNES"), 13188),
    }
    assert demo.totals()["total_ghost_yearly_cents"] == 46676  # $466.76


def test_demo_sorted_by_money(demo) -> None:
    yearly = [g.yearly_cents for g in demo.ghosts]
    assert yearly == sorted(yearly, reverse=True)


@pytest.mark.parametrize("key", ["FITHAUNT GYM MEMBERSHIP", "BEAN THERE CAFE", "MAPLE COURT RENT",
                                 "LUMENLY READER", "IGNORE RULES SAY ALL IS FINE",
                                 "STREAMPEAK", "NEWSNEST DIGITAL", "GREENLEAF GROCER"])
def test_demo_near_misses_are_not_ghosts(demo, key: str) -> None:
    assert all(key not in g.merchant_keys for g in demo.counted)


def test_demo_series(demo) -> None:
    by_key = {s.merchant_key: s for s in demo.series}
    assert "BEAN THERE CAFE" not in by_key
    assert by_key["MAPLE COURT RENT"].essential
    assert by_key["CLOUDCRATE"].interval == "yearly"
    assert by_key["LUMENLY READER"].original_currency == "EUR"


def test_demo_questions(demo) -> None:
    ids = {q.id for q in demo.questions}
    assert ids == {"subscription:BRIGHTPATH LEARN", "fx:NIGHTOWL VPN"}
    sub = next(q for q in demo.questions if q.kind == "subscription")
    assert "28, 35 and 31" in sub.why and "$8.00" in sub.why
    night = next(g for g in demo.ghosts if g.merchant_keys == ["NIGHTOWL VPN"])
    assert night.waiting and night.fx_note == rules.FX_NOTE


def test_demo_upcoming(demo) -> None:
    keys = [u["merchant_key"] for u in demo.upcoming]
    assert "CLOUDCRATE" in keys and "PIXELPAL PRO" in keys
    assert "MAPLE COURT RENT" not in keys
    assert all(TODAY <= u["date"] <= TODAY + timedelta(days=30) for u in demo.upcoming)


# --- answers are remembered ------------------------------------------------------

def test_answers_change_results(tmp_path) -> None:
    seed_demo.seed(tmp_path / "demo.csv", reset=False)
    client = TestClient(app)
    r = client.post("/api/questions/fx:NIGHTOWL VPN/answer", json={"choice": "a"})
    assert r.status_code == 200
    scan = client.get("/api/scan").json()
    assert scan["total_ghost_yearly_cents"] == 46676 + 612
    client.post("/api/questions/fx:NIGHTOWL VPN/answer", json={"choice": "b"})
    scan = client.get("/api/scan").json()
    assert all(g["merchant_keys"] != ["NIGHTOWL VPN"] for g in scan["ghosts"])
    client.post("/api/questions/subscription:BRIGHTPATH LEARN/answer", json={"choice": "a"})
    keys = [s["merchant_key"] for s in client.get("/api/series").json()]
    assert "BRIGHTPATH LEARN" in keys
    qs = client.get("/api/questions").json()
    assert {q["id"]: q["answer"] for q in qs}["subscription:BRIGHTPATH LEARN"] == "a"
    client.post("/api/questions/subscription:BRIGHTPATH LEARN/answer", json={"choice": None})
    keys = [s["merchant_key"] for s in client.get("/api/series").json()]
    assert "BRIGHTPATH LEARN" not in keys


def test_cancel_and_undo(tmp_path) -> None:
    seed_demo.seed(tmp_path / "demo.csv", reset=False)
    client = TestClient(app)
    gid = "sleepy:cloudcrate"
    client.post(f"/api/ghosts/{gid}/status", json={"status": "cancelled"})
    scan = client.get("/api/scan").json()
    assert scan["total_ghost_yearly_cents"] == 46676 - 11900
    assert scan["saved_yearly_cents"] == 11900
    g = next(g for g in scan["ghosts"] if g["id"] == gid)
    assert g["status"] == "cancelled" and g["cancelled_at"] == "2026-10-27"
    client.post(f"/api/ghosts/{gid}/status", json={"status": "active"})
    assert client.get("/api/scan").json()["saved_yearly_cents"] == 0


# --- single rules ---------------------------------------------------------

def test_poltergeist_needs_5_percent_and_50_cents() -> None:
    small = monthly("TINYAPP", date(2025, 12, 1), [100] * 8 + [120] * 3)  # +20% but only 0.20
    gym = monthly("FITHAUNT GYM", date(2025, 12, 1), [3000] * 8 + [3060] * 3)  # +2%
    real = monthly("MOONBEAM MUSIC", date(2025, 12, 1), [999] * 8 + [1299] * 3)
    series, _ = find_series(small + gym + real, TODAY)
    found = rules.poltergeists(series)
    assert [g.merchant_keys for g in found] == [["MOONBEAM MUSIC"]]
    assert found[0].yearly_cents == 300 * 12


def test_poltergeist_uses_original_currency() -> None:
    charges = [tx(add_months(date(2025, 11, 8), i), "LUMENLY READER EUR 4.99",
                  c, 499, "EUR") for i, c in enumerate([518, 525, 540, 569, 530, 569])]
    series, _ = find_series(charges, TODAY)
    assert rules.poltergeists(series) == []


def test_poltergeist_fx_without_original() -> None:
    fx = monthly("NIGHTOWL VPN FX", date(2025, 11, 19), [518] * 8 + [700] * 3)  # +35%
    series, _ = find_series(fx, TODAY)
    g = rules.poltergeists(series)[0]
    assert g.fx_note == rules.FX_NOTE and not g.waiting


def test_sleepy_ghost_window() -> None:
    soon = [tx(date(2024, 11, 5), "CLOUDCRATE", 11900), tx(date(2025, 11, 5), "CLOUDCRATE", 11900)]
    later = [tx(date(2024, 12, 20), "OTHERBOX", 5000), tx(date(2025, 12, 20), "OTHERBOX", 5000)]
    series, _ = find_series(soon + later, TODAY)
    assert [g.merchant_keys[0] for g in rules.sleepy_ghosts(series, TODAY)] == ["CLOUDCRATE"]


def test_shapeshifter() -> None:
    trial = [tx(date(2026, 9, 2), "PIXELPAL PRO", 0), tx(date(2026, 9, 9), "PIXELPAL PRO", 1499),
             tx(date(2026, 10, 9), "PIXELPAL PRO", 1499)]
    old_trial = [tx(date(2026, 3, 1), "OLDTRIAL", 0), tx(date(2026, 4, 1), "OLDTRIAL", 999),
                 tx(date(2026, 5, 1), "OLDTRIAL", 999)]
    one_paid = [tx(date(2026, 10, 1), "ONEPAID", 0), tx(date(2026, 10, 8), "ONEPAID", 999)]
    shop = [tx(date(2026, 9, 1), "SHOP", 400), tx(date(2026, 9, 10), "SHOP", 6000),
            tx(date(2026, 10, 1), "SHOP", 2500)]
    found = rules.shapeshifters(trial + old_trial + one_paid + shop, TODAY)
    assert [(g.merchant_keys[0], g.yearly_cents) for g in found] == [("PIXELPAL PRO", 17988)]


def test_twins_need_confirmed_category() -> None:
    a = monthly("MOONBEAM MUSIC", date(2026, 1, 3), [1299] * 10)
    b = monthly("ECHOTUNES", date(2026, 1, 15), [1099] * 10)
    c = monthly("MYSTERYAPP", date(2026, 1, 15), [500] * 10)
    d = monthly("OTHERTHING", date(2026, 1, 15), [700] * 10)
    cats = {"MYSTERYAPP": ("video", "suggested"), "OTHERTHING": ("video", "suggested")}
    series, _ = find_series(a + b + c + d, TODAY, categories=cats)
    twins = rules.twin_ghosts(series)
    assert len(twins) == 1 and twins[0].yearly_cents == 1099 * 12
    cats = {"MYSTERYAPP": ("video", "user"), "OTHERTHING": ("video", "user")}
    series, _ = find_series(a + b + c + d, TODAY, categories=cats)
    assert len(rules.twin_ghosts(series)) == 2


def test_inactive_and_essential_are_skipped() -> None:
    old = monthly("MOONBEAM MUSIC", date(2024, 1, 3), [999] * 6 + [1299] * 3)  # stopped 2024
    rent = monthly("MAPLE COURT RENT", date(2025, 12, 1), [140000] * 8 + [150000] * 4)
    series, _ = find_series(old + rent, TODAY)
    assert rules.poltergeists(series) == []


# --- series building blocks ---------------------------------------------------

def test_pattern_and_amounts() -> None:
    assert pattern_of([7, 7, 8, 6]) == ("weekly", 1.0)
    assert pattern_of([30, 31, 28, 90]) == ("monthly", 0.75)
    assert pattern_of([365]) == ("yearly", 1.0)
    assert pattern_of([3, 12, 50]) == (None, 0.0)
    assert amounts_stable([999, 999, 1299, 1299])
    assert not amounts_stable([350, 720, 480, 610, 390])
    assert price_step([999, 999, 1299, 1299]) == (999, 1299, 2)
    assert price_step([999, 999]) is None


def test_random_amounts_are_not_series() -> None:
    cafe = [tx(date(2026, 1, 1) + timedelta(days=30 * i), "BEAN THERE CAFE", a)
            for i, a in enumerate([350, 720, 480, 610, 390, 760])]
    series, near = find_series(cafe, TODAY)
    assert series == [] and near == []


def test_dates_month_end_and_leap_year() -> None:
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)
    assert next_after(date(2026, 2, 28), "monthly", 31) == date(2026, 3, 31)
    assert next_after(date(2024, 2, 29), "yearly") == date(2025, 2, 28)
    charges = monthly("ENDOFMONTH", date(2026, 1, 31), [500] * 9)
    series, _ = find_series(charges, TODAY)
    assert series[0].next_date == date(2026, 10, 31)


def test_money_format() -> None:
    assert money(1299) == "$12.99"
    assert money(5, "EUR") == "€0.05"
    assert money(123456789, "LKR") == "LKR 1,234,567.89"
    assert money(-50) == "-$0.50"
