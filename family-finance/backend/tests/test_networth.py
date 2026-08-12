"""Net worth balance estimation and month-over-month delta. All account
names, institutions, and amounts fabricated.

Two real bugs this covers, both reported against real user data:

1. The "estimate from running transaction total" fallback was applying to
   every account type, not just credit cards as documented — producing a
   wildly wrong "balance" for an asset account (e.g. a chequing account
   showing tens of thousands negative) that was never meant to lean on that
   assumption in the first place.
2. The month-over-month delta compared *all* of this month's accounts
   against only the *subset* of accounts that happened to have data from
   before this month — so an account getting its first-ever balance
   snapshot (e.g. a mortgage entered for the first time) looked like a
   swing of its entire balance, when really there's no "last month" to
   compare it to at all.
"""

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Account, AccountBalance, AccountType, Transaction
from app.networth import balance_for_account
from app.routers.networth import summary

TODAY = date.today()
FIRST_OF_MONTH = TODAY.replace(day=1)
BEFORE_THIS_MONTH = FIRST_OF_MONTH - timedelta(days=5)


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _account(db, name, account_type):
    account = Account(name=name, account_type=account_type)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def _txn(db, account_id, day, amount):
    db.add(Transaction(account_id=account_id, trans_date=day, description="x", amount=amount))
    db.commit()


def _snapshot(db, account_id, as_of, balance):
    db.add(AccountBalance(account_id=account_id, as_of_date=as_of, balance=balance))
    db.commit()


# --- balance estimate fallback is credit-card only --------------------------


def test_credit_card_with_no_snapshot_estimates_from_transactions(db):
    card = _account(db, "Sample Mastercard", AccountType.credit_card)
    _txn(db, card.id, BEFORE_THIS_MONTH, 500.00)
    balance, as_of, estimated = balance_for_account(db, card)
    assert balance == 500.00
    assert estimated is True


def test_chequing_with_no_snapshot_does_not_estimate_from_transactions(db):
    """This is the exact shape of the real bug: a chequing account with
    years of transactions but no manual snapshot should say "no balance
    recorded", not synthesize a number from a running total that was never
    a valid proxy for an asset account's real-world balance."""
    chequing = _account(db, "Sample Chequing", AccountType.chequing)
    _txn(db, chequing.id, BEFORE_THIS_MONTH, -50000.00)
    balance, as_of, estimated = balance_for_account(db, chequing)
    assert balance is None
    assert estimated is False


def test_any_account_type_with_a_real_snapshot_still_uses_it(db):
    savings = _account(db, "Sample Savings", AccountType.savings)
    _snapshot(db, savings.id, TODAY, 12345.67)
    balance, as_of, estimated = balance_for_account(db, savings)
    assert balance == 12345.67
    assert estimated is False


# --- month-over-month delta excludes newly-tracked accounts -----------------


def test_an_accounts_first_ever_snapshot_this_month_does_not_distort_the_delta(db):
    """Reproduces the user's report: adding a mortgage's first-ever balance
    snapshot today should not read as a huge net-worth swing — there is no
    prior data point for it to be compared against."""
    mortgage = _account(db, "Sample Mortgage", AccountType.mortgage)
    _snapshot(db, mortgage.id, TODAY, 241050.68)

    result = summary(db=db)
    assert result.liabilities_total == 241050.68
    assert result.delta is None
    assert result.accounts_with_history == 0
    assert result.accounts_total == 1


def test_an_account_with_real_history_contributes_its_true_delta(db):
    savings = _account(db, "Sample Savings", AccountType.savings)
    _snapshot(db, savings.id, BEFORE_THIS_MONTH, 1000.00)
    _snapshot(db, savings.id, TODAY, 1200.00)

    result = summary(db=db)
    assert result.delta == pytest.approx(200.00)
    assert result.accounts_with_history == 1


def test_mixed_accounts_delta_only_reflects_the_one_with_history(db):
    """The core regression test for the reported bug: one account has real
    month-over-month history, another (like the mortgage) is brand new this
    month. The delta must equal only the tracked account's own change —
    never the new account's entire balance."""
    savings = _account(db, "Sample Savings", AccountType.savings)
    _snapshot(db, savings.id, BEFORE_THIS_MONTH, 1000.00)
    _snapshot(db, savings.id, TODAY, 1200.00)

    mortgage = _account(db, "Sample Mortgage", AccountType.mortgage)
    _snapshot(db, mortgage.id, TODAY, 241050.68)

    result = summary(db=db)
    assert result.delta == pytest.approx(200.00)
    assert result.accounts_with_history == 1
    assert result.accounts_total == 2
    # Both accounts still count fully toward the current totals.
    assert result.assets_total == 1200.00
    assert result.liabilities_total == 241050.68


def test_a_liability_paying_down_shows_as_a_positive_delta(db):
    """Paying down debt should read as net worth going UP, not down —
    liabilities are subtracted from net worth, so a shrinking liability
    balance is a positive change."""
    card = _account(db, "Sample Mastercard", AccountType.credit_card)
    _snapshot(db, card.id, BEFORE_THIS_MONTH, 2000.00)
    _snapshot(db, card.id, TODAY, 1500.00)

    result = summary(db=db)
    assert result.delta == pytest.approx(500.00)


def test_no_accounts_have_any_history_delta_is_none(db):
    _account(db, "Sample Chequing", AccountType.chequing)
    result = summary(db=db)
    assert result.delta is None
    assert result.net_worth_prev_month is None
    assert result.accounts_with_history == 0


def test_accounts_are_ordered_by_sort_order_then_name(db):
    b = _account(db, "B Account", AccountType.chequing)
    a = _account(db, "A Account", AccountType.chequing)
    # Explicitly reverse the natural sort_order (creation order) so name
    # order alone would disagree with it — sort_order must win.
    a.sort_order, b.sort_order = 5, 1
    db.commit()

    result = summary(db=db)
    names = [acc.name for acc in result.accounts]
    assert names == ["B Account", "A Account"]
