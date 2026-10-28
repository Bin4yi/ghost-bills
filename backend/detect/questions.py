"""Penny's question cards: "I ask you instead of guessing."

Code creates a question when a rule is unsure. Answers are stored and
re-applied on every scan, so the user is never asked twice.
"""

from __future__ import annotations

from backend.detect.series import NearMiss
from backend.detect.util import money
from backend.models import Ghost, Question
from backend.normalize import display_name


def subscription_question(n: NearMiss) -> Question:
    gaps = ", ".join(str(g) for g in n.gaps[:-1]) + f" and {n.gaps[-1]}" if len(n.gaps) > 1 \
        else str(n.gaps[0])
    name = display_name(n.merchant_key)
    return Question(
        id=f"subscription:{n.merchant_key}", kind="subscription", ref_id=n.merchant_key,
        tag="Not sure it is a subscription",
        question=f"Is {name} a subscription?",
        why=(f"{name} charged {money(n.amount_cents, n.currency)} {n.count} times. "
             f"The gaps were {gaps} days, so only {n.fitting} of {len(n.gaps)} look {n.interval}."),
        choice_a="Yes, it is a subscription", choice_b="No, it is not")


def date_order_question(signature: str, sample: str, count: int) -> Question:
    return Question(
        id=f"date_order:{signature}", kind="date_order", ref_id=signature,
        tag="Unclear date",
        question=f"Is {sample} day first or month first?",
        why=(f"All {count} dates in your file have both numbers at 12 or below, "
             f"so {sample} could be read two ways."),
        choice_a="Day first (31/12)", choice_b="Month first (12/31)")


def fx_question(g: Ghost) -> Question:
    key = g.merchant_keys[0]
    return Question(
        id=f"fx:{key}", kind="fx", ref_id=key,
        tag="Maybe the exchange rate",
        question=f"Did {display_name(key)} really raise its price?",
        why=(f"{g.evidence[0]}, then {g.evidence[1]}. It is charged in a foreign currency and the statement does not "
             f"show the original amount, so the change may be the exchange rate."),
        choice_a="A real price rise", choice_b="Just the exchange rate")


def with_answers(questions: list[Question], answers: dict[str, str]) -> list[Question]:
    for q in questions:
        a = answers.get(q.id)
        q.answer = a if a in ("a", "b") else None  # type: ignore[assignment]
    return questions
