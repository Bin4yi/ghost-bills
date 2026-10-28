from collections import Counter
from datetime import date

from backend import db, seed_demo


def test_seed_is_deterministic(tmp_path) -> None:
    a = seed_demo.to_csv(seed_demo.build_rows())
    b = seed_demo.to_csv(seed_demo.build_rows())
    assert a == b


def test_seed_loads(tmp_path) -> None:
    result = seed_demo.seed(tmp_path / "demo.csv", reset=False)
    txs = db.load_transactions()
    assert result["imported"] == len(txs) > 600
    keys = Counter(t.merchant_key for t in txs)
    assert keys["MOONBEAM MUSIC"] == 15
    assert keys["CLOUDCRATE"] == 2
    assert keys["PIXELPAL PRO"] == 3
    assert "NORTHWIND PAYROLL SALARY" not in keys  # money in is skipped
    assert min(t.date for t in txs) >= date(2024, 8, 28)
    assert max(t.date for t in txs) <= date(2026, 10, 27)
    lumen = [t for t in txs if t.merchant_key == "LUMENLY READER"]
    assert {t.original_amount_cents for t in lumen} == {499}
    assert len({t.amount_cents for t in lumen}) > 3
