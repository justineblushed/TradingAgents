"""Account management: editing, deleting, and reordering. All account
names fabricated.

Editing and deleting exist specifically so a mis-typed account (e.g. a
chequing account quick-added as a Credit Card, which is exactly what
happened to real users) can be corrected in place without losing its
transaction history, rather than needing to be deleted and recreated.
"""

from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Account, AccountBalance, AccountType, Transaction
from app.routers.accounts import create_account, delete_account, list_accounts, move_account, update_account
from app.schemas import AccountCreate, AccountMoveRequest, AccountUpdate


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


# --- create assigns an incrementing sort_order -------------------------------


def test_new_accounts_get_incrementing_sort_order(db):
    first = create_account(AccountCreate(name="First"), db=db)
    second = create_account(AccountCreate(name="Second"), db=db)
    assert second.sort_order > first.sort_order


# --- editing lets a mis-typed account be corrected in place ------------------


def test_editing_account_type_fixes_a_mis_typed_account(db):
    """The Simplii Chequing / "quick-add always defaults to credit card"
    bug, resolved in place — the account keeps its identity and any
    attached data, only its type changes."""
    account = _account(db, "Simplii Chequing", AccountType.credit_card)
    updated = update_account(account.id, AccountUpdate(account_type="chequing"), db=db)
    assert updated.account_type == "chequing"
    assert updated.is_liability is False


def test_editing_name_alone_leaves_other_fields_untouched(db):
    account = _account(db, "Old Name", AccountType.savings)
    account.credit_limit = None
    db.commit()
    updated = update_account(account.id, AccountUpdate(name="New Name"), db=db)
    assert updated.name == "New Name"
    assert updated.account_type == "savings"


def test_editing_a_nonexistent_account_404s(db):
    with pytest.raises(HTTPException) as exc_info:
        update_account(999, AccountUpdate(name="Nope"), db=db)
    assert exc_info.value.status_code == 404


# --- deleting is blocked while an account still has real data ---------------


def test_deleting_an_empty_account_succeeds(db):
    account = _account(db, "Accidental Duplicate", AccountType.other_asset)
    delete_account(account.id, db=db)
    assert db.get(Account, account.id) is None


def test_deleting_an_account_with_transactions_is_blocked(db):
    account = _account(db, "Sample Chequing", AccountType.chequing)
    db.add(Transaction(account_id=account.id, trans_date=date(2026, 7, 1), description="x", amount=10.0))
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        delete_account(account.id, db=db)
    assert exc_info.value.status_code == 400
    # The account must survive the failed attempt.
    assert db.get(Account, account.id) is not None


def test_deleting_an_account_with_balance_snapshots_is_blocked(db):
    account = _account(db, "Sample Mortgage", AccountType.mortgage)
    db.add(AccountBalance(account_id=account.id, as_of_date=date(2026, 7, 1), balance=200000.0))
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        delete_account(account.id, db=db)
    assert exc_info.value.status_code == 400


def test_deleting_a_nonexistent_account_404s(db):
    with pytest.raises(HTTPException) as exc_info:
        delete_account(999, db=db)
    assert exc_info.value.status_code == 404


# --- reordering is scoped to the account's own asset/liability group --------


def test_moving_an_account_up_swaps_with_its_neighbour(db):
    a = _account(db, "A", AccountType.chequing)
    b = _account(db, "B", AccountType.chequing)
    a.sort_order, b.sort_order = 0, 1
    db.commit()

    move_account(b.id, AccountMoveRequest(direction="up"), db=db)
    names = [acc.name for acc in list_accounts(db=db)]
    assert names == ["B", "A"]


def test_moving_the_top_account_up_is_a_no_op(db):
    a = _account(db, "A", AccountType.chequing)
    b = _account(db, "B", AccountType.chequing)
    a.sort_order, b.sort_order = 0, 1
    db.commit()

    move_account(a.id, AccountMoveRequest(direction="up"), db=db)
    names = [acc.name for acc in list_accounts(db=db)]
    assert names == ["A", "B"]


def test_moving_the_bottom_account_down_is_a_no_op(db):
    a = _account(db, "A", AccountType.chequing)
    b = _account(db, "B", AccountType.chequing)
    a.sort_order, b.sort_order = 0, 1
    db.commit()

    move_account(b.id, AccountMoveRequest(direction="down"), db=db)
    names = [acc.name for acc in list_accounts(db=db)]
    assert names == ["A", "B"]


def test_reordering_never_crosses_the_asset_liability_boundary(db):
    """Assets and liabilities render as two separate lists on the Net Worth
    page, so moving an asset "down" must never swap it past a liability —
    that swap would have no visible effect and would corrupt the other
    group's order."""
    asset = _account(db, "Sample Savings", AccountType.savings)
    liability = _account(db, "Sample Mortgage", AccountType.mortgage)
    asset.sort_order, liability.sort_order = 0, 1
    db.commit()

    move_account(asset.id, AccountMoveRequest(direction="down"), db=db)
    refreshed_asset = db.get(Account, asset.id)
    refreshed_liability = db.get(Account, liability.id)
    assert refreshed_asset.sort_order == 0
    assert refreshed_liability.sort_order == 1


def test_moving_a_nonexistent_account_404s(db):
    with pytest.raises(HTTPException) as exc_info:
        move_account(999, AccountMoveRequest(direction="up"), db=db)
    assert exc_info.value.status_code == 404
