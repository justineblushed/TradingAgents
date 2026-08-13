"""Detection and correction of income-kind transactions stored with the
wrong sign. All merchants and amounts fabricated.

This is the exact mismatch that drags total_income negative on /summary,
/sankey, and the category drill-down: this app's convention is
negative = money in, and every one of those reads a category's raw total
and negates it to show a positive number. A transaction stored the wrong
way round — usually left over from a statement imported before its CSV's
own sign convention was reconciled — pulls those totals down instead of up.
"""

from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Account, AccountType, Category, CategoryKind, Transaction
from app.routers.dashboard import summary
from app.routers.transactions import fix_sign_issues, list_sign_issues
from app.schemas import SignIssueFixRequest

MONTH = "2026-07"


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(Account(name="Sample Chequing", account_type=AccountType.chequing))
    session.add(Category(name="Employment Income", kind=CategoryKind.income))
    session.add(Category(name="Rental Income", kind=CategoryKind.income))
    session.add(Category(name="Groceries", kind=CategoryKind.expense))
    session.commit()
    try:
        yield session
    finally:
        session.close()


def _cat(db, name):
    return db.query(Category).filter(Category.name == name).first()


def _txn(db, day, description, amount, category):
    row = Transaction(
        account_id=1,
        trans_date=day,
        description=description,
        amount=amount,
        category_id=_cat(db, category).id,
    )
    db.add(row)
    db.commit()
    return row


# --- detection -----------------------------------------------------------


def test_a_correctly_signed_income_row_is_not_flagged(db):
    _txn(db, date(2026, 7, 14), "PAYROLL DEPOSIT", -3200.00, "Employment Income")
    assert list_sign_issues(db) == []


def test_a_positive_income_row_is_flagged(db):
    bad = _txn(db, date(2026, 7, 14), "PAYROLL DEPOSIT", 3200.00, "Employment Income")
    issues = list_sign_issues(db)
    assert len(issues) == 1
    assert issues[0].id == bad.id
    assert issues[0].amount == 3200.00
    assert issues[0].category == "Employment Income"
    assert issues[0].account_name == "Sample Chequing"
    assert issues[0].direction == "income_positive"


def test_a_normal_positive_expense_charge_is_not_flagged(db):
    _txn(db, date(2026, 7, 3), "SAMPLE GROCER", 120.00, "Groceries")
    assert list_sign_issues(db) == []


def test_an_expense_row_stored_negative_is_flagged_as_lower_confidence(db):
    """A negative amount on an expense category is often an ordinary
    refund netted against that category on purpose, not a bug — but it
    can also be the mirror image of the income-direction bug: a debit
    imported with the wrong sign under a real expense category. It's
    surfaced for review with its own direction, rather than either being
    invisible (the old behaviour) or treated as unambiguous the way an
    income-positive row is."""
    bad = _txn(db, date(2026, 7, 9), "SAMPLE CAR PAYMENT", -392.50, "Groceries")
    issues = list_sign_issues(db)
    assert len(issues) == 1
    assert issues[0].id == bad.id
    assert issues[0].direction == "expense_negative"


def test_multiple_issues_across_categories_and_accounts_are_all_found(db):
    _txn(db, date(2026, 7, 14), "PAYROLL DEPOSIT", 3200.00, "Employment Income")
    _txn(db, date(2026, 7, 5), "SAMPLE RENT", 500.00, "Rental Income")
    _txn(db, date(2026, 7, 3), "SAMPLE GROCER", 120.00, "Groceries")
    issues = list_sign_issues(db)
    assert {i.category for i in issues} == {"Employment Income", "Rental Income"}


def test_issues_are_returned_newest_first(db):
    _txn(db, date(2026, 6, 1), "OLD PAYROLL", 3000.00, "Employment Income")
    _txn(db, date(2026, 7, 14), "NEW PAYROLL", 3200.00, "Employment Income")
    issues = list_sign_issues(db)
    assert [i.description for i in issues] == ["NEW PAYROLL", "OLD PAYROLL"]


def test_a_flagged_row_actually_drags_total_income_negative(db):
    """Confirms the detector is finding the real cause, not a coincidence:
    fixing it should be what brings /summary back to a sane number."""
    _txn(db, date(2026, 7, 3), "SAMPLE GROCER", 50.00, "Groceries")
    _txn(db, date(2026, 7, 14), "PAYROLL DEPOSIT", 3200.00, "Employment Income")
    assert summary(month=MONTH, db=db).total_income == -3200.00


# --- fixing ---------------------------------------------------------------


def test_fixing_a_flagged_row_flips_its_sign(db):
    bad = _txn(db, date(2026, 7, 14), "PAYROLL DEPOSIT", 3200.00, "Employment Income")
    result = fix_sign_issues(SignIssueFixRequest(transaction_ids=[bad.id]), db)
    assert result.fixed == 1
    assert result.already_ok == 0
    db.refresh(bad)
    assert bad.amount == -3200.00


def test_fixing_resolves_the_downstream_total(db):
    _txn(db, date(2026, 7, 3), "SAMPLE GROCER", 50.00, "Groceries")
    bad = _txn(db, date(2026, 7, 14), "PAYROLL DEPOSIT", 3200.00, "Employment Income")
    fix_sign_issues(SignIssueFixRequest(transaction_ids=[bad.id]), db)
    assert summary(month=MONTH, db=db).total_income == 3200.00


def test_fixing_an_already_correct_row_is_a_safe_no_op(db):
    good = _txn(db, date(2026, 7, 14), "PAYROLL DEPOSIT", -3200.00, "Employment Income")
    result = fix_sign_issues(SignIssueFixRequest(transaction_ids=[good.id]), db)
    assert result.fixed == 0
    assert result.already_ok == 1
    db.refresh(good)
    assert good.amount == -3200.00  # untouched


def test_fixing_a_normal_positive_expense_row_is_refused_even_if_requested(db):
    """The fix endpoint re-validates every id itself rather than trusting
    the caller's list — a stale or tampered request must not flip a row
    that was never actually a sign issue."""
    row = _txn(db, date(2026, 7, 3), "SAMPLE GROCER", 120.00, "Groceries")
    result = fix_sign_issues(SignIssueFixRequest(transaction_ids=[row.id]), db)
    assert result.fixed == 0
    assert result.already_ok == 1
    db.refresh(row)
    assert row.amount == 120.00


def test_fixing_an_expense_negative_row_works_when_explicitly_requested(db):
    """Unlike income-positive, an expense-negative row isn't pre-selected
    by default (it could be a genuine refund) — but once a user reviews
    it and decides it's actually wrong, fixing it should work the same
    way as the unambiguous direction."""
    bad = _txn(db, date(2026, 7, 9), "SAMPLE CAR PAYMENT", -392.50, "Groceries")
    result = fix_sign_issues(SignIssueFixRequest(transaction_ids=[bad.id]), db)
    assert result.fixed == 1
    assert result.already_ok == 0
    db.refresh(bad)
    assert bad.amount == 392.50


def test_fixing_a_nonexistent_id_is_silently_skipped(db):
    result = fix_sign_issues(SignIssueFixRequest(transaction_ids=[999]), db)
    assert result.fixed == 0
    assert result.already_ok == 0


def test_an_empty_request_is_refused(db):
    with pytest.raises(HTTPException) as excinfo:
        fix_sign_issues(SignIssueFixRequest(transaction_ids=[]), db)
    assert excinfo.value.status_code == 400


def test_fixing_leaves_other_flagged_rows_untouched(db):
    bad1 = _txn(db, date(2026, 7, 14), "PAYROLL DEPOSIT", 3200.00, "Employment Income")
    bad2 = _txn(db, date(2026, 7, 5), "SAMPLE RENT", 500.00, "Rental Income")
    fix_sign_issues(SignIssueFixRequest(transaction_ids=[bad1.id]), db)
    db.refresh(bad2)
    assert bad2.amount == 500.00  # not selected, not touched
    assert len(list_sign_issues(db)) == 1
