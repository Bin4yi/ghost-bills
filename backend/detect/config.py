"""Every threshold the detector uses. Shown in the UI under "How we decide"."""

MIN_CHARGES = 3            # charges needed to call something a series
MIN_CHARGES_YEARLY = 2     # yearly plans: two charges a year apart is enough
WEEKLY = (6, 8)            # days between charges
MONTHLY = (27, 33)
YEARLY = (355, 375)
PATTERN_SHARE = 0.7        # share of gaps that must fit the pattern
QUESTION_SHARE = 0.5       # 50-70% fit -> Penny asks instead of guessing
AMOUNT_TOLERANCE = 0.10    # amounts within +-10% of the median count as "same price"
PRICE_UP_PCT = 0.05        # Poltergeist: new price at least 5% higher...
PRICE_UP_MIN_CENTS = 50    # ...and at least 0.50 higher
RENEW_SOON_DAYS = 30       # Sleepy Ghost: yearly renewal within 30 days
TRIAL_MAX_CENTS = 100      # Shapeshifter: a "trial" charge of 0.00-1.00...
TRIAL_SHARE = 0.10         # ...or at most 10% of the later price
TRIAL_WINDOW_DAYS = 90     # the trial started in the last 90 days
ACTIVE_FACTOR = 1.5        # active if last charge is within 1.5 x interval of today
FX_PRICE_UP_PCT = 0.15     # foreign line with no original amount: sure rise only at 15%

INTERVAL_DAYS = {"weekly": 7, "monthly": 30, "yearly": 365}
PER_YEAR = {"weekly": 52, "monthly": 12, "yearly": 1}
PATTERNS = {"weekly": WEEKLY, "monthly": MONTHLY, "yearly": YEARLY}

ESSENTIAL_WORDS = ("RENT", "MORTGAGE", "LOAN", "ELECTRIC", "WATER", "INSURANCE")
FOREIGN_WORDS = ("FX", "FOREIGN", "INTL", "INTERNATIONAL", "NON-STERLING", "CROSS-BORDER")


def as_dict() -> dict:
    """Public view of the numbers for the "How we decide" panel."""
    return {k: v for k, v in globals().items()
            if k.isupper() and k not in ("INTERVAL_DAYS", "PER_YEAR", "PATTERNS")}
