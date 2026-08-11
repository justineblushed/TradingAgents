"""Recurring-charge detection tests. All merchants and amounts fabricated.

The point of these is mostly the *negative* cases: what this module refuses
to call a bill matters more than what it accepts, because a wrong prediction
on the dashboard is worse than a missing one.
"""

from datetime import date, timedelta

from app.recurring import detect_recurring, next_payday, normalize_description

TODAY = date(2026, 8, 11)


def _row(description, amount, day, account_id=1, category="Utilities", kind="expense"):
    return {
        "description": description,
        "amount": amount,
        "trans_date": day,
        "account_id": account_id,
        "account_name": "Sample Chequing",
        "category": category,
        "kind": kind,
    }


def _monthly(description, amount, count, start=date(2026, 3, 14), **kw):
    return [
        _row(description, amount, start + timedelta(days=30 * i), **kw)
        for i in range(count)
    ]


# --- description normalization ------------------------------------------------


def test_store_numbers_collapse_to_one_merchant():
    assert normalize_description("SAMPLE COFFEE #4821") == normalize_description(
        "SAMPLE COFFEE #0093"
    )


def test_different_merchants_stay_separate():
    assert normalize_description("SAMPLE COFFEE") != normalize_description(
        "SAMPLE GROCER"
    )


def test_reference_numbers_and_punctuation_are_stripped():
    assert normalize_description("HYDRO BILL PMT 2026-07-15 REF 88213") == "hydro bill pmt ref"


# --- what counts as recurring -------------------------------------------------


def test_a_steady_monthly_charge_is_detected():
    series = detect_recurring(_monthly("SAMPLE INTERNET", 89.99, 5), TODAY)
    assert len(series) == 1
    assert series[0].cadence == "monthly"
    assert series[0].occurrences == 5
    assert series[0].typical_amount == 89.99
    assert series[0].amount_varies is False


def test_next_date_projects_one_cycle_past_the_last_charge():
    rows = _monthly("SAMPLE INTERNET", 89.99, 5, start=date(2026, 4, 2))
    series = detect_recurring(rows, TODAY)
    last = rows[-1]["trans_date"]
    assert series[0].last_date == last
    assert (series[0].next_date - last).days == 30


def test_two_charges_are_not_enough():
    assert detect_recurring(_monthly("SAMPLE INTERNET", 89.99, 2), TODAY) == []


def test_irregular_visits_are_not_a_bill():
    # Same merchant, but the gaps are all over the place — a coffee habit,
    # not a subscription. Averaging these would land near "monthly".
    days = [0, 3, 40, 44, 95, 96]
    rows = [
        _row("SAMPLE COFFEE", 6.75, date(2026, 3, 1) + timedelta(days=d)) for d in days
    ]
    assert detect_recurring(rows, TODAY) == []


def test_same_day_repeats_do_not_count_as_cycles():
    day = date(2026, 7, 4)
    rows = [_row("SAMPLE PARKING", 8.0, day) for _ in range(5)]
    assert detect_recurring(rows, TODAY) == []


def test_biweekly_cadence_is_recognized():
    rows = [
        _row("SAMPLE GYM", 32.0, date(2026, 5, 1) + timedelta(days=14 * i))
        for i in range(6)
    ]
    series = detect_recurring(rows, TODAY)
    assert series and series[0].cadence == "biweekly"


def test_a_wandering_amount_is_flagged_with_a_range():
    rows = [
        _row("SAMPLE HYDRO", amount, date(2026, 3, 20) + timedelta(days=30 * i))
        for i, amount in enumerate([120.0, 180.0, 95.0, 210.0])
    ]
    series = detect_recurring(rows, TODAY)
    assert series[0].amount_varies is True
    assert series[0].amount_low == 95.0
    assert series[0].amount_high == 210.0


def test_the_same_merchant_on_two_accounts_stays_two_series():
    rows = _monthly("SAMPLE STREAMING", 16.99, 4, account_id=1) + _monthly(
        "SAMPLE STREAMING", 16.99, 4, account_id=2
    )
    assert len(detect_recurring(rows, TODAY)) == 2


def test_a_cancelled_subscription_stops_being_reported():
    # Ran monthly through last year, then stopped — long past due.
    rows = _monthly("SAMPLE OLD SERVICE", 19.99, 4, start=date(2025, 1, 5))
    assert detect_recurring(rows, TODAY) == []


def test_series_come_back_soonest_first():
    rows = _monthly("SAMPLE A", 10.0, 4, start=date(2026, 5, 2)) + _monthly(
        "SAMPLE B", 20.0, 4, start=date(2026, 5, 20)
    )
    series = detect_recurring(rows, TODAY)
    assert [s.next_date for s in series] == sorted(s.next_date for s in series)


# --- payday projection --------------------------------------------------------


def test_payday_projects_from_biweekly_stubs():
    stubs = [date(2026, 7, 10) + timedelta(days=14 * i) for i in range(4)]
    result = next_payday(stubs, TODAY)
    assert result is not None
    projected, basis, gap = result
    assert gap == 14
    assert "biweekly" in basis
    assert projected > TODAY


def test_payday_rolls_forward_past_a_gap_in_data_entry():
    # Stubs stopped being entered months ago; the projection must still land
    # in the future rather than reporting a payday that already happened.
    stubs = [date(2026, 1, 2) + timedelta(days=14 * i) for i in range(3)]
    projected, _basis, _gap = next_payday(stubs, TODAY)
    assert projected >= TODAY


def test_one_stub_is_not_a_rhythm():
    assert next_payday([date(2026, 8, 7)], TODAY) is None
    assert next_payday([], TODAY) is None


def test_semi_monthly_pay_is_recognized():
    stubs = [
        date(2026, 5, 15),
        date(2026, 5, 31),
        date(2026, 6, 15),
        date(2026, 6, 30),
        date(2026, 7, 15),
        date(2026, 7, 31),
    ]
    _projected, basis, _gap = next_payday(stubs, TODAY)
    assert "semi-monthly" in basis
