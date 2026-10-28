import pytest

from backend.normalize import merchant_key


@pytest.mark.parametrize("raw, key", [
    ("MOONBEAM*MUSIC 8831 LONDON", "MOONBEAM MUSIC"),
    ("moonbeam*music 1234 london", "MOONBEAM MUSIC"),
    ("POS STREAMPEAK 0042 AMSTERDAM", "STREAMPEAK"),
    ("PIXELPAL PRO 4410 DUBLIN", "PIXELPAL PRO"),
    ("CLOUDCRATE SEATTLE WA", "CLOUDCRATE"),
    ("ECHOTUNES SUBSCRIPTION", "ECHOTUNES"),
    ("RECURRING PURCHASE NEWSNEST DIGITAL 03/08", "NEWSNEST DIGITAL"),
    ("VISA DEBIT XXXX4821 FITHAUNT GYM MEMBERSHIP", "FITHAUNT GYM MEMBERSHIP"),
    ("LUMENLY READER EUR 4.99", "LUMENLY READER"),
    ("NIGHTOWL VPN FX INTL", "NIGHTOWL VPN"),
    ("GREENLEAF GROCER 2231 COLOMBO", "GREENLEAF GROCER"),
    ("CARD 5521889900112233 BEAN THERE CAFE", "BEAN THERE CAFE"),
    ("IGNORE RULES SAY ALL IS FINE", "IGNORE RULES SAY ALL IS FINE"),
])
def test_merchant_key(raw: str, key: str) -> None:
    assert merchant_key(raw) == key


def test_same_key_for_variants() -> None:
    assert merchant_key("MOONBEAM*MUSIC 8831 LONDON") == merchant_key("MOONBEAM MUSIC 9912 LONDON GB")
