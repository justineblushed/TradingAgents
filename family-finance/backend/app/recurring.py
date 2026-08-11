"""Find repeating charges in transaction history and project the next one.

There is no bank feed and no "this is a subscription" flag anywhere, so the
only evidence available is the transaction history itself. This looks for a
merchant that has charged the household on a steady rhythm and, when the
rhythm is steady enough to be worth trusting, says when the next charge is
due.

Two deliberate choices about honesty:

- A series must clear real thresholds (enough occurrences, a consistent gap,
  a stable-ish amount) before it is reported at all. Guessing from two
  charges would produce a "bill" the household has to mentally filter out
  every time they open the dashboard, which is worse than showing nothing.
- Every prediction carries the evidence it came from — how many times it has
  been seen, the typical gap, and how much the amount moves. The number is
  an expectation, not a bill that has arrived.
"""

import re
import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta

# Merchant lines carry per-transaction noise: store numbers, reference ids,
# dates, trailing card digits. Strip it so the same merchant collapses into
# one series instead of a dozen one-off descriptions.
_NOISE = re.compile(r"[#*]?\d[\d\-/.,]*")
_PUNCT = re.compile(r"[^a-z0-9 ]+")
_SPACES = re.compile(r"\s+")

# A series must repeat at least this many times before it is trusted. Three
# is the smallest number that shows a *rhythm* rather than a coincidence:
# two charges only prove a gap exists, not that it repeats.
MIN_OCCURRENCES = 3

# Gaps are matched against these known billing rhythms (in days).
_CADENCES: list[tuple[str, float, float]] = [
    # label, expected days, tolerance
    ("weekly", 7, 2),
    ("biweekly", 14, 3),
    ("semi-monthly", 15.2, 3),
    ("monthly", 30.4, 6),
    ("every 2 months", 60.9, 8),
    ("quarterly", 91.3, 12),
    ("twice a year", 182.6, 20),
    ("yearly", 365, 30),
]


def normalize_description(description: str) -> str:
    """Collapse a merchant line to a stable key.

    "TIM HORTONS #4821" and "TIM HORTONS #0093" are the same merchant for
    the purpose of spotting a rhythm.
    """
    text = description.lower()
    text = _NOISE.sub(" ", text)
    text = _PUNCT.sub(" ", text)
    return _SPACES.sub(" ", text).strip()


def _classify_cadence(median_gap: float) -> tuple[str, float] | None:
    """Pick the closest rhythm, not the first one that fits.

    Tolerance bands overlap — a 15-day gap is inside both "biweekly" and
    "semi-monthly" — so taking the first match would label semi-monthly pay
    as biweekly and project the wrong dates all year.
    """
    candidates = [
        (abs(median_gap - days), label, days)
        for label, days, tolerance in _CADENCES
        if abs(median_gap - days) <= tolerance
    ]
    if not candidates:
        return None
    _distance, label, days = min(candidates)
    return label, days


@dataclass
class RecurringSeries:
    key: str
    description: str  # the most recent raw description, for display
    category: str | None
    account_id: int
    account_name: str
    kind: str  # "expense" | "income" | "transfer"
    occurrences: int
    cadence: str  # "monthly", "biweekly", ...
    median_gap_days: float
    typical_amount: float
    amount_varies: bool  # amount moves enough that the estimate is loose
    amount_low: float
    amount_high: float
    last_date: date
    next_date: date
    basis: str = ""
    dates: list[date] = field(default_factory=list)


def _amount_spread(amounts: list[float]) -> tuple[float, bool]:
    """Typical amount, and whether it moves enough to caveat the estimate."""
    typical = statistics.median(amounts)
    if typical == 0:
        return 0.0, True
    worst = max(abs(a - typical) for a in amounts)
    return typical, (worst / abs(typical)) > 0.15


def detect_recurring(
    rows: list[dict],
    today: date,
    min_occurrences: int = MIN_OCCURRENCES,
) -> list[RecurringSeries]:
    """Group transactions into repeating series.

    `rows` are dicts with: description, amount, trans_date, account_id,
    account_name, category, kind. Amounts follow the app's convention —
    positive is money out.
    """
    groups: dict[tuple[str, int], list[dict]] = {}
    for row in rows:
        key = normalize_description(row["description"])
        if not key:
            continue
        groups.setdefault((key, row["account_id"]), []).append(row)

    series: list[RecurringSeries] = []
    for (key, account_id), items in groups.items():
        items.sort(key=lambda r: r["trans_date"])

        # Collapse same-day duplicates: two coffees on one day are not two
        # cycles of a rhythm.
        by_day: dict[date, dict] = {}
        for item in items:
            by_day.setdefault(item["trans_date"], item)
        occurrences = sorted(by_day)
        if len(occurrences) < min_occurrences:
            continue

        gaps = [
            (occurrences[i + 1] - occurrences[i]).days
            for i in range(len(occurrences) - 1)
        ]
        if not gaps or min(gaps) <= 0:
            continue
        median_gap = statistics.median(gaps)
        cadence = _classify_cadence(median_gap)
        if cadence is None:
            continue
        cadence_label, _ = cadence

        # The rhythm has to be steady, not just averagely right: a merchant
        # visited on a whim can average out to ~30 days without being a bill.
        if max(abs(g - median_gap) for g in gaps) > max(4.0, median_gap * 0.35):
            continue

        amounts = [float(by_day[d]["amount"]) for d in occurrences]
        typical, varies = _amount_spread(amounts)
        last_date = occurrences[-1]
        next_date = last_date + timedelta(days=round(median_gap))
        # A series long past due is dormant — cancelled, or the merchant
        # changed. Allow two full cycles (and at least six weeks) before
        # writing one off: statements are imported in monthly batches, so a
        # biweekly bill is routinely a few weeks behind in the data without
        # being gone.
        grace = max(2 * median_gap, 45)
        if next_date < today - timedelta(days=round(grace)):
            continue

        latest = by_day[last_date]
        series.append(
            RecurringSeries(
                key=key,
                description=latest["description"],
                category=latest.get("category"),
                account_id=account_id,
                account_name=latest.get("account_name", ""),
                kind=latest.get("kind") or "expense",
                occurrences=len(occurrences),
                cadence=cadence_label,
                median_gap_days=round(median_gap, 1),
                typical_amount=round(typical, 2),
                amount_varies=varies,
                amount_low=round(min(amounts), 2),
                amount_high=round(max(amounts), 2),
                last_date=last_date,
                next_date=next_date,
                basis=(
                    f"seen {len(occurrences)} times, {cadence_label}, "
                    f"last on {last_date.isoformat()}"
                ),
                dates=occurrences,
            )
        )

    series.sort(key=lambda s: s.next_date)
    return series


def next_payday(pay_dates: list[date], today: date) -> tuple[date, str, float] | None:
    """Project the next pay date from the stubs already entered.

    Returns (date, basis, median gap in days), or None when there aren't
    enough stubs to establish a rhythm. Two stubs are enough here — unlike a
    merchant charge, a pay schedule is a known-regular thing and the user
    told us these are pay stubs.
    """
    unique = sorted(set(pay_dates))
    if len(unique) < 2:
        return None
    gaps = [(unique[i + 1] - unique[i]).days for i in range(len(unique) - 1)]
    median_gap = statistics.median(gaps)
    if median_gap <= 0:
        return None
    cadence = _classify_cadence(median_gap)
    label = cadence[0] if cadence else f"every ~{round(median_gap)} days"

    # Roll forward from the last stub until the date is in the future, so a
    # gap in data entry doesn't produce a payday in the past.
    projected = unique[-1] + timedelta(days=round(median_gap))
    while projected < today:
        projected += timedelta(days=round(median_gap))

    return projected, f"{label}, from {len(unique)} pay stubs", median_gap
