import json
from datetime import date
from typing import Any

import pytest

from backend import db
from backend.llm import enrich, grounding
from backend.llm.ollama_client import OllamaError
from backend.models import Ghost, Series

GHOST = Ghost(
    id="poltergeist:moonbeam-music", type="poltergeist", series_ids=["MOONBEAM MUSIC"],
    merchant_keys=["MOONBEAM MUSIC"], yearly_cents=3600, display_name="Moonbeam Music",
    evidence=["$9.99 every month from Aug 2025 to Jul 2026", "$12.99 since 3 Aug 2026",
              "$3.00 more each time, $36.00 more per year"])

GOOD = {
    "display_name": "Moonbeam Music",
    "category_suggestion": "music",
    "story": "I spoke with your statement. Moonbeam Music now takes $12.99, not $9.99.",
    "epitaph": "Here lies a price rise nobody asked for.",
    "explain": "Since 3 Aug 2026 you pay $12.99 each month. That is $36.00 more per year. "
               "Keep it only if you still listen.",
    "cancel_email": {
        "subject": "Please cancel my Moonbeam Music subscription",
        "body": "Hello,\n\nPlease cancel my Moonbeam Music subscription and confirm by email."
                "\n\nThank you,\n[YOUR NAME]\n[YOUR ACCOUNT EMAIL]",
    },
}


def with_(**changes: Any) -> dict[str, Any]:
    out = json.loads(json.dumps(GOOD))
    for k, v in changes.items():
        if k.startswith("email_"):
            out["cancel_email"][k[6:]] = v
        else:
            out[k] = v
    return out


class FakeLLM:
    def __init__(self, *answers: dict[str, Any]) -> None:
        self.answers = list(answers)
        self.prompts: list[str] = []

    def __call__(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        self.prompts.append(user)
        return self.answers.pop(0)


FACTS = enrich.facts_for(GHOST)


def check(out: dict[str, Any]) -> list[str]:
    return grounding.check(out, FACTS, GHOST.merchant_keys)


def test_good_output_passes() -> None:
    assert check(GOOD) == []


@pytest.mark.parametrize("bad, reason", [
    (with_(explain="It now costs $14.99 each month."), "amount"),
    (with_(story="Moonbeam raised the price on 9 Sep 2026."), "date"),
    (with_(explain="Cancel at https://moonbeam.example/cancel today."), "link"),
    (with_(explain="Cancel at moonbeam.com today."), "link"),
    (with_(email_body="Call 0800 123 4567. [YOUR NAME] [YOUR ACCOUNT EMAIL]"), "phone"),
    (with_(email_body="Write to help@moonbeam.example [YOUR NAME] [YOUR ACCOUNT EMAIL]"), "email"),
    (with_(display_name="StreamPeak"), "display_name"),
    (with_(epitaph="Here lies a very long epitaph that keeps on going and going past the limit"),
     "too long"),
    (with_(email_body="Please cancel. Thanks."), "[YOUR NAME]"),
])
def test_grounding_rejects(bad: dict[str, Any], reason: str) -> None:
    reasons = check(bad)
    assert any(reason in r for r in reasons), reasons


def test_grounding_allows_partial_dates_and_plain_numbers() -> None:
    ok = with_(explain="Since Aug 2026 you pay $12.99. That is 3 dollars more, $36 a year.")
    assert check(ok) == []


def test_enrich_good_first_try() -> None:
    llm = FakeLLM(GOOD)
    fields, source, _ = enrich.enrich_one(GHOST, llm)
    assert source == "gemma" and fields["story"] == GOOD["story"]
    assert "<data>" in llm.prompts[0] and "$12.99 since 3 Aug 2026" in llm.prompts[0]


def test_enrich_retries_with_reason() -> None:
    llm = FakeLLM(with_(explain="Cancel at https://x.example"), GOOD)
    _, source, _ = enrich.enrich_one(GHOST, llm)
    assert source == "gemma"
    assert "rejected because" in llm.prompts[1] and "link" in llm.prompts[1]


def test_two_failures_give_template() -> None:
    bad = with_(explain="It now costs $14.99.")
    fields, source, _ = enrich.enrich_one(GHOST, FakeLLM(bad, bad))
    assert source == "template"
    assert "[YOUR NAME]" in fields["cancel_email"]["body"]
    assert grounding.check(fields, FACTS, GHOST.merchant_keys) == []


def test_ollama_down_gives_template() -> None:
    def down(*_: Any) -> dict[str, Any]:
        raise OllamaError("not running")
    _, source, _ = enrich.enrich_one(GHOST, down)
    assert source == "offline"
    result = enrich.enrich_all([GHOST], [], down)
    assert result["enriched"] == 0 and "error" in result
    assert enrich.cached(GHOST) is None  # retried once Gemma is back


def test_templates_pass_grounding_for_every_type() -> None:
    for kind in ("poltergeist", "sleepy", "shapeshifter", "twins"):
        g = GHOST.model_copy(update={"type": kind})
        assert grounding.check(enrich.template(g), enrich.facts_for(g), g.merchant_keys) == []


def test_cache_and_suggestion() -> None:
    s = Series(id="NIGHTOWL VPN", merchant_key="NIGHTOWL VPN", interval="monthly",
               amounts=[518, 569], dates=[date(2026, 9, 19), date(2026, 10, 19)],
               last_date=date(2026, 10, 19), next_date=date(2026, 11, 19), active=True)
    g = GHOST.model_copy(update={"merchant_keys": ["NIGHTOWL VPN"], "id": "poltergeist:nightowl",
                                 "display_name": "Nightowl Vpn"})
    out = with_(display_name="NightOwl VPN", category_suggestion="vpn",
                story="A spirit raised its price.", explain="The price went up by $3.00.",
                email_subject="Please cancel NightOwl VPN",
                email_body="Please cancel NightOwl VPN. [YOUR NAME] [YOUR ACCOUNT EMAIL]")
    llm = FakeLLM(out)
    assert enrich.enrich_all([g], [s], llm)["enriched"] == 1
    assert enrich.enrich_all([g], [s], llm)["enriched"] == 0  # cached, no new call
    assert db.get_row("categories", "merchant_key", "NIGHTOWL VPN")["source"] == "suggested"
    assert enrich.apply_cached_or_template([g]) == 0
    assert g.text_source == "gemma" and g.display_name == "NightOwl VPN"
