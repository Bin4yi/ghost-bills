from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from backend import db
from backend.app import app
from backend.importer import csv_import as ci
from backend.importer import service
from backend.models import ColumnMapping

from .conftest import FIXTURES


def load(name: str) -> tuple[list[str], list[list[str]], ColumnMapping]:
    text = ci.decode((FIXTURES / name).read_bytes())
    header, rows = ci.read_table(text)
    mapping = ci.guess_mapping(header, rows)
    assert mapping is not None
    return header, rows, mapping


@pytest.mark.parametrize("raw, expected", [
    ("12.00", Decimal("12.00")),
    ("-9.99", Decimal("-9.99")),
    ("(12.00)", Decimal("-12.00")),
    ("$1,234.56", Decimal("1234.56")),
    ("1.234,56", Decimal("1234.56")),
    ("12,99", Decimal("12.99")),
    ("€ 4,99", Decimal("4.99")),
    ("Rs. 2,500.00", Decimal("2500.00")),
    ("12.00-", Decimal("-12.00")),
    ("", None),
    ("abc", None),
])
def test_parse_amount(raw: str, expected: Decimal | None) -> None:
    assert ci.parse_amount(raw) == expected


def test_to_cents_rounds_half_up() -> None:
    assert ci.to_cents(Decimal("0.005")) == 1
    assert ci.to_cents(Decimal("12.994")) == 1299
    assert ci.to_cents(Decimal("12.995")) == 1300


@pytest.mark.parametrize("values, order", [
    (["2026-08-03", "2026-12-31"], "ymd"),
    (["03/08/2026", "21/08/2026"], "dmy"),
    (["08/03/2026", "08/21/2026"], "mdy"),
    (["01/02/2026", "02/03/2026"], None),
])
def test_detect_date_order(values: list[str], order: str | None) -> None:
    assert ci.detect_date_order(values) == order


def test_parse_dates_edge_cases() -> None:
    assert ci.parse_date("29/02/2024", "dmy") == date(2024, 2, 29)
    assert ci.parse_date("12/31/2026", "mdy") == date(2026, 12, 31)
    assert ci.parse_date("3 Aug 2026", "dmy") == date(2026, 8, 3)
    with pytest.raises(ValueError):
        ci.parse_date("29/02/2026", "dmy")  # not a leap year


def test_semicolon_debit_credit() -> None:
    header, rows, m = load("semicolon_eu.csv")
    assert header[1] == "Details"
    assert m.debit == 2 and m.credit == 3 and m.amount is None
    assert m.date_order == "dmy"
    txs = ci.build_transactions(rows, m)
    assert [t.amount_cents for t in txs] == [1299, 123456, 1549]  # salary left out
    assert txs[0].merchant_key == "MOONBEAM MUSIC"


def test_iso_positive_with_original_columns() -> None:
    _, rows, m = load("iso_positive.csv")
    assert m.original_amount == 3 and m.original_currency == 4
    assert m.date_order == "ymd"
    txs = ci.build_transactions(rows, m)
    # No negatives in the column: every row is money out, the $0.00 trial is kept.
    assert [t.amount_cents for t in txs] == [0, 541, 1499, 560, 101499]
    lumen = [t for t in txs if t.merchant_key == "LUMENLY READER"]
    assert [(t.amount_cents, t.original_amount_cents, t.original_currency) for t in lumen] == [
        (541, 499, "EUR"), (560, 499, "EUR")]


def test_ambiguous_dates_need_user() -> None:
    _, rows, m = load("ambiguous_us.csv")
    assert m.date_order is None
    txs = ci.build_transactions(rows, m, date_order="mdy")
    assert [t.date for t in txs] == [date(2026, 1, 2), date(2026, 2, 3), date(2026, 3, 4)]


def test_original_amount_in_description() -> None:
    assert ci.original_from_text("LUMENLY READER EUR 4.99") == (499, "EUR")
    assert ci.original_from_text("Foo USD 1,299.00 bar") == (129900, "USD")
    assert ci.original_from_text("NIGHTOWL VPN FX INTL") is None


def test_preview_and_commit_api() -> None:
    client = TestClient(app)
    data = (FIXTURES / "ambiguous_us.csv").read_bytes()
    r = client.post("/api/import/preview", files={"file": ("s.csv", data, "text/csv")})
    assert r.status_code == 200
    body = r.json()
    assert body["needs_user"] is True
    assert len(body["rows"]) == 4
    mapping = body["mapping"] | {"date_order": "mdy"}
    r = client.post("/api/import/commit", json={"upload_id": body["upload_id"], "mapping": mapping})
    assert r.json()["imported"] == 3
    # The profile is remembered for the next file with the same header.
    r = client.post("/api/import/preview", files={"file": ("s.csv", data, "text/csv")})
    assert r.json()["from_profile"] is True
    assert r.json()["needs_user"] is False


def test_reimport_with_order() -> None:
    text = (FIXTURES / "ambiguous_us.csv").read_text()
    header, rows = ci.read_table(text)
    m = ci.guess_mapping(header, rows)
    assert m is not None
    assert service.import_text(text, m)["needs_user"] is True
    assert db.load_transactions()[0].date == date(2026, 2, 1)  # read as day/month
    service.reimport_with_order("mdy")
    assert db.load_transactions()[0].date == date(2026, 1, 2)


def test_bad_file() -> None:
    client = TestClient(app)
    r = client.post("/api/import/preview", files={"file": ("x.csv", b"hello\nworld", "text/csv")})
    assert r.status_code == 400
