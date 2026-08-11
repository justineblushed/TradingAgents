"""Category drill-down and appearance. All data fabricated.

The contract that matters: the drill-down total must equal what the
dashboard chart shows for the same category and month. If those two ever
disagree, clicking a bar becomes a way to lose trust in both numbers.
"""

from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Account, AccountType, Category, CategoryKind, Transaction
from app.routers.dashboard import _shift_month, category_detail, summary

MONTH = "2026-07"


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(Account(name="Sample Visa", account_type=AccountType.credit_card))
    session.add(
        Category(
            name="Groceries",
            kind=CategoryKind.expense,
            group_name="Food",
            color="#15803d",
            emoji="🛒",
        )
    )
    session.add(Category(name="Employment Income", kind=CategoryKind.income))
    session.add(Category(name="Credit Card Payment", kind=CategoryKind.transfer))
    session.commit()
    try:
        yield session
    finally:
        session.close()


def _cat(db, name):
    return db.query(Category).filter(Category.name == name).first()


def _txn(db, day, description, amount, category="Groceries"):
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


# --- month totals -------------------------------------------------------------


def test_total_and_count_for_the_month(db):
    _txn(db, date(2026, 7, 3), "SAMPLE GROCER", 120.00)
    _txn(db, date(2026, 7, 18), "SAMPLE GROCER", 80.50)
    detail = category_detail(category="Groceries", month=MONTH, db=db)
    assert detail.total == 200.50
    assert detail.transaction_count == 2


def test_other_months_are_excluded_from_the_total(db):
    _txn(db, date(2026, 7, 3), "SAMPLE GROCER", 120.00)
    _txn(db, date(2026, 6, 30), "SAMPLE GROCER", 999.00)
    _txn(db, date(2026, 8, 1), "SAMPLE GROCER", 999.00)
    assert category_detail(category="Groceries", month=MONTH, db=db).total == 120.00


def test_a_refund_is_netted_off_not_counted_as_income(db):
    _txn(db, date(2026, 7, 3), "SAMPLE GROCER", 120.00)
    _txn(db, date(2026, 7, 9), "SAMPLE GROCER REFUND", -20.00)
    detail = category_detail(category="Groceries", month=MONTH, db=db)
    assert detail.total == 100.00
    assert detail.transaction_count == 2


def test_the_drill_down_total_matches_the_dashboard_chart(db):
    """The whole point of clicking a bar is to see what's inside it."""
    _txn(db, date(2026, 7, 3), "SAMPLE GROCER", 120.00)
    _txn(db, date(2026, 7, 9), "SAMPLE GROCER REFUND", -20.00)
    _txn(db, date(2026, 7, 11), "SAMPLE GROCER", 45.25)

    chart = summary(month=MONTH, db=db).by_category["Groceries"]
    assert category_detail(category="Groceries", month=MONTH, db=db).total == chart


def test_income_reads_as_a_positive_number(db):
    # Income is stored negative (money in); showing "-$3,200" on an income
    # page would read as a loss.
    _txn(db, date(2026, 7, 15), "PAYROLL DEPOSIT", -3200.00, category="Employment Income")
    detail = category_detail(category="Employment Income", month=MONTH, db=db)
    assert detail.total == 3200.00
    assert detail.kind == "income"


def test_transfers_can_still_be_drilled_into(db):
    # They're excluded from spending totals, but "what did I pay off?" is a
    # fair question and the transactions exist.
    _txn(db, date(2026, 7, 20), "PAYMENT THANK YOU", -500.00, category="Credit Card Payment")
    detail = category_detail(category="Credit Card Payment", month=MONTH, db=db)
    assert detail.transaction_count == 1


def test_uncategorized_is_a_real_destination(db):
    _txn(db, date(2026, 7, 5), "SAMPLE UNKNOWN", 42.00, category=None)
    detail = category_detail(category="Uncategorized", month=MONTH, db=db)
    assert detail.total == 42.00
    assert detail.transaction_count == 1


def test_an_unknown_category_404s_rather_than_showing_an_empty_page(db):
    with pytest.raises(HTTPException) as excinfo:
        category_detail(category="Not A Category", month=MONTH, db=db)
    assert excinfo.value.status_code == 404


def test_a_month_with_nothing_returns_an_empty_but_valid_detail(db):
    detail = category_detail(category="Groceries", month="2026-02", db=db)
    assert detail.total == 0
    assert detail.transactions == []
    assert detail.average_of_history is None


# --- history ------------------------------------------------------------------


def test_history_covers_twelve_months_ending_with_the_one_requested(db):
    detail = category_detail(category="Groceries", month=MONTH, db=db)
    assert len(detail.history) == 12
    assert detail.history[-1].month == MONTH
    assert detail.history[-1].is_current is True
    assert detail.history[0].month == "2025-08"
    assert sum(1 for p in detail.history if p.is_current) == 1


def test_history_totals_line_up_with_each_month(db):
    _txn(db, date(2026, 5, 4), "SAMPLE GROCER", 300.00)
    _txn(db, date(2026, 7, 4), "SAMPLE GROCER", 100.00)
    by_month = {p.month: p.total for p in category_detail("Groceries", MONTH, db).history}
    assert by_month["2026-05"] == 300.00
    assert by_month["2026-06"] == 0.0
    assert by_month["2026-07"] == 100.00


def test_typical_excludes_the_current_month(db):
    _txn(db, date(2026, 5, 4), "SAMPLE GROCER", 100.00)
    _txn(db, date(2026, 6, 4), "SAMPLE GROCER", 200.00)
    _txn(db, date(2026, 7, 4), "SAMPLE GROCER", 900.00)  # the outlier being viewed
    detail = category_detail(category="Groceries", month=MONTH, db=db)
    assert detail.average_of_history == 150.00  # not dragged up by the 900


def test_typical_ignores_empty_months(db):
    """Months before the account existed would otherwise drag the average
    toward zero and make every real month look like an overspend."""
    _txn(db, date(2026, 6, 4), "SAMPLE GROCER", 200.00)
    _txn(db, date(2026, 7, 4), "SAMPLE GROCER", 210.00)
    detail = category_detail(category="Groceries", month=MONTH, db=db)
    assert detail.average_of_history == 200.00  # one month of history, not /11


# --- budget -------------------------------------------------------------------


def test_over_budget_is_reported_when_it_is_over(db):
    _cat(db, "Groceries").monthly_budget = 150
    db.commit()
    _txn(db, date(2026, 7, 4), "SAMPLE GROCER", 210.00)
    detail = category_detail(category="Groceries", month=MONTH, db=db)
    assert detail.monthly_budget == 150.0
    assert detail.over_budget == 60.0


def test_under_budget_reports_no_overage_rather_than_a_negative_one(db):
    _cat(db, "Groceries").monthly_budget = 300
    db.commit()
    _txn(db, date(2026, 7, 4), "SAMPLE GROCER", 210.00)
    assert category_detail(category="Groceries", month=MONTH, db=db).over_budget is None


# --- appearance ---------------------------------------------------------------


def test_appearance_comes_through_on_the_detail(db):
    detail = category_detail(category="Groceries", month=MONTH, db=db)
    assert detail.color == "#15803d"
    assert detail.emoji == "🛒"


def test_month_shifting_crosses_year_boundaries(db):
    assert _shift_month("2026-01", -1) == "2025-12"
    assert _shift_month("2026-12", 1) == "2027-01"
    assert _shift_month("2026-07", -12) == "2025-07"
    assert _shift_month("2026-07", 0) == "2026-07"
