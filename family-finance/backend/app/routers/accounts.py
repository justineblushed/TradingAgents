from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Account, AccountBalance, Transaction
from app.schemas import (
    AccountBalanceCreate,
    AccountBalanceOut,
    AccountCreate,
    AccountMoveRequest,
    AccountOut,
    AccountUpdate,
)

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountOut])
def list_accounts(db: Session = Depends(get_db)):
    return db.query(Account).order_by(Account.sort_order, Account.name).all()


@router.post("", response_model=AccountOut)
def create_account(payload: AccountCreate, db: Session = Depends(get_db)):
    max_order = db.query(func.max(Account.sort_order)).scalar()
    next_order = max_order + 1 if max_order is not None else 0
    account = Account(**payload.model_dump(), sort_order=next_order)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.patch("/{account_id}", response_model=AccountOut)
def update_account(
    account_id: int, payload: AccountUpdate, db: Session = Depends(get_db)
):
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(404, "Account not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(account, field, value)
    db.commit()
    db.refresh(account)
    return account


@router.delete("/{account_id}", status_code=204)
def delete_account(account_id: int, db: Session = Depends(get_db)):
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(404, "Account not found")

    transaction_count = (
        db.query(func.count(Transaction.id))
        .filter(Transaction.account_id == account_id)
        .scalar()
    )
    balance_count = (
        db.query(func.count(AccountBalance.id))
        .filter(AccountBalance.account_id == account_id)
        .scalar()
    )
    if transaction_count or balance_count:
        raise HTTPException(
            400,
            f"Can't delete \"{account.name}\" — it still has {transaction_count} "
            f"transaction(s) and {balance_count} balance snapshot(s) attached. "
            "Move or delete those first if you really want this account gone.",
        )

    db.delete(account)
    db.commit()


@router.post("/{account_id}/move", response_model=list[AccountOut])
def move_account(
    account_id: int, payload: AccountMoveRequest, db: Session = Depends(get_db)
):
    """Swaps this account's display position with its neighbour, but only
    within its own group (an asset never swaps past a liability or vice
    versa) — the two groups are rendered as separate lists, so reordering
    across them wouldn't have any visible effect anyway."""
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(404, "Account not found")

    siblings = [
        a
        for a in db.query(Account).order_by(Account.sort_order, Account.name).all()
        if a.is_liability == account.is_liability
    ]
    index = next(i for i, a in enumerate(siblings) if a.id == account.id)
    neighbor_index = index - 1 if payload.direction == "up" else index + 1

    if 0 <= neighbor_index < len(siblings):
        neighbor = siblings[neighbor_index]
        account.sort_order, neighbor.sort_order = neighbor.sort_order, account.sort_order
        db.commit()

    return db.query(Account).order_by(Account.sort_order, Account.name).all()


@router.post("/{account_id}/balances", response_model=AccountBalanceOut)
def record_balance(
    account_id: int, payload: AccountBalanceCreate, db: Session = Depends(get_db)
):
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(404, "Account not found")
    balance = AccountBalance(
        account_id=account_id, as_of_date=payload.as_of_date, balance=payload.balance
    )
    db.add(balance)
    db.commit()
    db.refresh(balance)
    return balance
