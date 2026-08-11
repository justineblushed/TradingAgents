"""Daily spending calendar endpoint. All merchants and amounts fabricated.

The property that matters most, as with the Sankey: whatever this grid
totals up for the month must equal what /summary reports for the same
month — a heatmap that disagrees with the KPI cards next to it would be
worse than no heatmap.
"""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Account, AccountType, Category, CategoryKind, Transaction
from app.routers.dashboard import calendar_view, summary

MONTH = "2026-07"  # July 2026: starts Wednesday, ends Friday, 31 days


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(Account(name="Sample Visa", account_type=AccountType.credit_card))
    session.add(Category(name="Groceries", kind=CategoryKind.expense))
    session.add(Category(name="Employment Income", kind=CategoryKind.income))
    session.add(Category(name="Credit Card Payment", kind=CategoryKind.transfer))
    session.commit()
    try:
        yield session
    finally:
        session.close()


def _cat(db, name):
    return db.query(Category).filter(Category.name == name).first()


def _txn(db, day, description, amount, category):
    db.add(
        Transaction(
            account_id=1,
            trans_date=day,
            description=description,
            amount=amount,
            category_id=_cat(db, category).id if category else None,
        )
    )
    db.commit()


def _day(result, d):
    return next(x for x in result.days if x.date == d)


# --- grid shape -----------------------------------------------------------


def test_grid_starts_on_a_monday_and_ends_on_a_sunday(db):
    result = calendar_view(month=MONTH, db=db)
    assert result.days[0].date.weekday() == 0  # Monday
    assert result.days[-1].date.weekday() == 6  # Sunday


def test_grid_is_always_a_whole_number_of_weeks(db):
    result = calendar_view(month=MONTH, db=db)
    assert len(result.days) % 7 == 0


def test_grid_covers_every_day_of_the_month(db):
    result = calendar_view(month=MONTH, db=db)
    in_month_dates = {d.date for d in result.days if d.in_month}
    assert in_month_dates == {date(2026, 7, day) for day in range(1, 32)}


def test_padding_days_are_marked_out_of_month(db):
    result = calendar_view(month=MONTH, db=db)
    # July 1, 2026 is a Wednesday, so Jun 29-30 pad the front.
    assert _day(result, date(2026, 6, 29)).in_month is False
    assert _day(result, date(2026, 7, 1)).in_month is True


def test_a_month_that_already_starts_on_monday_still_gets_full_weeks(db):
    # 2026-06 starts on a Monday.
    result = calendar_view(month="2026-06", db=db)
    assert result.days[0].date == date(2026, 6, 1)
    assert len(result.days) % 7 == 0


# --- day totals -------------------------------------------------------------


def test_a_days_spending_is_the_sum_of_that_days_purchases(db):
    _txn(db, date(2026, 7, 3), "SAMPLE GROCER", 40.00, "Groceries")
    _txn(db, date(2026, 7, 3), "SAMPLE CAFE", 6.50, "Groceries")
    result = calendar_view(month=MONTH, db=db)
    assert _day(result, date(2026, 7, 3)).spending == 46.50
    assert _day(result, date(2026, 7, 3)).transaction_count == 2


def test_a_refund_nets_against_the_same_day(db):
    _txn(db, date(2026, 7, 3), "SAMPLE GROCER", 120.00, "Groceries")
    _txn(db, date(2026, 7, 3), "SAMPLE GROCER REFUND", -20.00, "Groceries")
    assert _day(calendar_view(month=MONTH, db=db), date(2026, 7, 3)).spending == 100.00


def test_income_and_spending_are_tracked_separately_on_the_same_day(db):
    _txn(db, date(2026, 7, 14), "SAMPLE GROCER", 50.00, "Groceries")
    _txn(db, date(2026, 7, 14), "PAYROLL DEPOSIT", -3200.00, "Employment Income")
    day = _day(calendar_view(month=MONTH, db=db), date(2026, 7, 14))
    assert day.spending == 50.00
    assert day.income == 3200.00


def test_transfers_are_excluded_same_as_the_dashboard(db):
    _txn(db, date(2026, 7, 20), "PAYMENT THANK YOU", -500.00, "Credit Card Payment")
    day = _day(calendar_view(month=MONTH, db=db), date(2026, 7, 20))
    assert day.spending == 0
    assert day.income == 0
    assert day.transaction_count == 0


def test_a_day_with_nothing_is_zero_not_missing(db):
    day = _day(calendar_view(month=MONTH, db=db), date(2026, 7, 10))
    assert day.spending == 0
    assert day.income == 0
    assert day.transaction_count == 0


def test_a_purchase_on_a_padding_day_still_shows_its_real_amount(db):
    """The padding day belongs to June, but a real June 29 purchase should
    still show up with its real number — the frontend dims it, but the
    data itself isn't hidden or zeroed."""
    _txn(db, date(2026, 6, 29), "SAMPLE GROCER", 75.00, "Groceries")
    day = _day(calendar_view(month=MONTH, db=db), date(2026, 6, 29))
    assert day.in_month is False
    assert day.spending == 75.00


# --- totals agree with /summary --------------------------------------------


def test_totals_match_the_dashboard_summary_for_the_same_month(db):
    _txn(db, date(2026, 7, 3), "SAMPLE GROCER", 120.00, "Groceries")
    _txn(db, date(2026, 7, 14), "PAYROLL DEPOSIT", -3200.00, "Employment Income")
    # Padding-day activity must NOT leak into this month's totals.
    _txn(db, date(2026, 6, 29), "SAMPLE GROCER", 999.00, "Groceries")

    dash = summary(month=MONTH, db=db)
    cal = calendar_view(month=MONTH, db=db)
    assert cal.total_spending == dash.total_spending
    assert cal.total_income == dash.total_income


def test_max_daily_spending_is_the_single_highest_day(db):
    _txn(db, date(2026, 7, 3), "SAMPLE GROCER", 40.00, "Groceries")
    _txn(db, date(2026, 7, 20), "SAMPLE ELECTRONICS", 400.00, "Groceries")
    result = calendar_view(month=MONTH, db=db)
    assert result.max_daily_spending == 400.00


def test_max_daily_spending_considers_padding_days_too(db):
    """The colour scale has to account for every cell actually drawn,
    including padding days — otherwise a big padding-day purchase would
    render hotter than the scale's own maximum implies."""
    _txn(db, date(2026, 6, 29), "SAMPLE ELECTRONICS", 900.00, "Groceries")
    _txn(db, date(2026, 7, 3), "SAMPLE GROCER", 40.00, "Groceries")
    result = calendar_view(month=MONTH, db=db)
    assert result.max_daily_spending == 900.00


def test_an_empty_month_returns_a_full_grid_of_zeros(db):
    result = calendar_view(month=MONTH, db=db)
    assert result.total_spending == 0
    assert result.total_income == 0
    assert result.max_daily_spending == 0
    assert all(d.spending == 0 and d.income == 0 for d in result.days)
