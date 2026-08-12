"""GET /transactions filtering by kind. All merchants and amounts
fabricated.

Lets the Dashboard's Spending and Income KPI cards link somewhere
meaningful — "kind=expense" should show exactly what that month's
Spending total is made of, and "kind=income" exactly what Income is made
of, matching the same is_spending logic used everywhere else (dashboard
summary, Sankey) rather than inventing a second definition.
"""

from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Account, AccountType, Category, CategoryKind, Transaction
from app.routers.transactions import delete_transaction, list_transactions

MONTH = "2026-07"


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(Account(name="Sample Chequing", account_type=AccountType.chequing))
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


def _txn(db, day, description, amount, category=None):
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


def test_kind_expense_returns_only_expense_category_rows(db):
    _txn(db, date(2026, 7, 3), "SAMPLE GROCER", 40.00, "Groceries")
    _txn(db, date(2026, 7, 15), "PAYROLL DEPOSIT", -3200.00, "Employment Income")
    rows = list_transactions(month=MONTH, kind="expense", db=db)
    assert [r.description for r in rows] == ["SAMPLE GROCER"]


def test_kind_income_returns_only_income_category_rows(db):
    _txn(db, date(2026, 7, 3), "SAMPLE GROCER", 40.00, "Groceries")
    _txn(db, date(2026, 7, 15), "PAYROLL DEPOSIT", -3200.00, "Employment Income")
    rows = list_transactions(month=MONTH, kind="income", db=db)
    assert [r.description for r in rows] == ["PAYROLL DEPOSIT"]


def test_kind_expense_includes_positive_uncategorized_rows(db):
    """Matches the is_spending fallback used elsewhere: an uncategorized
    positive-amount row reads as spending, not as neither."""
    _txn(db, date(2026, 7, 3), "SAMPLE UNKNOWN CHARGE", 25.00)
    rows = list_transactions(month=MONTH, kind="expense", db=db)
    assert [r.description for r in rows] == ["SAMPLE UNKNOWN CHARGE"]


def test_kind_income_includes_negative_uncategorized_rows(db):
    _txn(db, date(2026, 7, 3), "SAMPLE UNKNOWN DEPOSIT", -25.00)
    rows = list_transactions(month=MONTH, kind="income", db=db)
    assert [r.description for r in rows] == ["SAMPLE UNKNOWN DEPOSIT"]


def test_kind_expense_excludes_transfers(db):
    _txn(db, date(2026, 7, 20), "PAYMENT THANK YOU", -500.00, "Credit Card Payment")
    rows = list_transactions(month=MONTH, kind="expense", db=db)
    assert rows == []
    rows = list_transactions(month=MONTH, kind="income", db=db)
    assert rows == []


def test_kind_combines_with_month_filter(db):
    _txn(db, date(2026, 7, 3), "SAMPLE JULY GROCER", 40.00, "Groceries")
    _txn(db, date(2026, 8, 3), "SAMPLE AUGUST GROCER", 40.00, "Groceries")
    rows = list_transactions(month=MONTH, kind="expense", db=db)
    assert [r.description for r in rows] == ["SAMPLE JULY GROCER"]


def test_an_invalid_kind_value_is_rejected(db):
    with pytest.raises(HTTPException) as exc_info:
        list_transactions(month=MONTH, kind="bogus", db=db)
    assert exc_info.value.status_code == 400


def test_no_kind_filter_returns_everything(db):
    _txn(db, date(2026, 7, 3), "SAMPLE GROCER", 40.00, "Groceries")
    _txn(db, date(2026, 7, 15), "PAYROLL DEPOSIT", -3200.00, "Employment Income")
    _txn(db, date(2026, 7, 20), "PAYMENT THANK YOU", -500.00, "Credit Card Payment")
    rows = list_transactions(month=MONTH, db=db)
    assert len(rows) == 3


def test_deleting_a_transaction_removes_it(db):
    """Lets a user clean up a duplicate the automated finder didn't catch —
    e.g. two copies that differ enough (or land far enough apart) that
    they weren't grouped — without going through the Duplicates page."""
    _txn(db, date(2026, 7, 3), "SAMPLE GROCER", 40.00, "Groceries")
    txn_id = list_transactions(month=MONTH, db=db)[0].id
    result = delete_transaction(txn_id, db=db)
    assert result == {"ok": True}
    assert list_transactions(month=MONTH, db=db) == []


def test_deleting_a_nonexistent_transaction_is_a_404(db):
    with pytest.raises(HTTPException) as exc_info:
        delete_transaction(999, db=db)
    assert exc_info.value.status_code == 404


def test_deleting_one_transaction_leaves_others_untouched(db):
    _txn(db, date(2026, 7, 3), "SAMPLE GROCER", 40.00, "Groceries")
    _txn(db, date(2026, 7, 15), "PAYROLL DEPOSIT", -3200.00, "Employment Income")
    rows = list_transactions(month=MONTH, db=db)
    grocer_id = next(r.id for r in rows if r.description == "SAMPLE GROCER")
    delete_transaction(grocer_id, db=db)
    remaining = list_transactions(month=MONTH, db=db)
    assert [r.description for r in remaining] == ["PAYROLL DEPOSIT"]
