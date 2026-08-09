from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Account, AccountBalance
from app.schemas import AccountBalanceCreate, AccountBalanceOut, AccountCreate, AccountOut

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountOut])
def list_accounts(db: Session = Depends(get_db)):
    return db.query(Account).all()


@router.post("", response_model=AccountOut)
def create_account(payload: AccountCreate, db: Session = Depends(get_db)):
    account = Account(**payload.model_dump())
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


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
