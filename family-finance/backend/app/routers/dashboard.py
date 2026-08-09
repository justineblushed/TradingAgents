from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.dateutil import month_bounds
from app.db import get_db
from app.models import Account, AccountType, CategoryKind, Transaction
from app.networth import balance_for_account
from app.schemas import CreditCardSummary, DashboardSummary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _current_month() -> str:
    return datetime.utcnow().strftime("%Y-%m")


@router.get("/summary", response_model=DashboardSummary)
def summary(month: str | None = None, db: Session = Depends(get_db)):
    month = month or _current_month()
    start, end = month_bounds(month)

    rows = (
        db.query(Transaction)
        .options(joinedload(Transaction.category))
        .filter(Transaction.trans_date >= start, Transaction.trans_date < end)
        .all()
    )
    # Transfers (e.g. a credit card payment from chequing) are money moving
    # between the household's own accounts, not spending or income — drop
    # them entirely rather than letting them inflate either total.
    rows = [r for r in rows if not (r.category and r.category.kind == CategoryKind.transfer)]

    total_income = -sum(float(r.amount) for r in rows if r.amount < 0)
    total_spending = sum(float(r.amount) for r in rows if r.amount > 0)

    by_category: dict[str, float] = defaultdict(float)
    for r in rows:
        if r.amount > 0:
            name = r.category.name if r.category else "Uncategorized"
            by_category[name] += float(r.amount)

    return DashboardSummary(
        month=month,
        total_spending=total_spending,
        total_income=total_income,
        net_cash_flow=total_income - total_spending,
        by_category=dict(by_category),
    )


@router.get("/credit-cards", response_model=list[CreditCardSummary])
def credit_cards(month: str | None = None, db: Session = Depends(get_db)):
    month = month or _current_month()
    start, end = month_bounds(month)

    accounts = (
        db.query(Account).filter(Account.account_type == AccountType.credit_card).all()
    )

    out: list[CreditCardSummary] = []
    for account in accounts:
        balance, as_of, estimated = balance_for_account(db, account)

        rows = (
            db.query(Transaction)
            .options(joinedload(Transaction.category))
            .filter(
                Transaction.account_id == account.id,
                Transaction.trans_date >= start,
                Transaction.trans_date < end,
            )
            .all()
        )
        month_spending = sum(
            float(r.amount)
            for r in rows
            if r.amount > 0 and not (r.category and r.category.kind == CategoryKind.transfer)
        )
        month_payments = -sum(
            float(r.amount)
            for r in rows
            if r.amount < 0 and r.category and r.category.kind == CategoryKind.transfer
        )

        credit_limit = float(account.credit_limit) if account.credit_limit else None
        available_credit = (
            credit_limit - balance if credit_limit is not None and balance is not None else None
        )

        out.append(
            CreditCardSummary(
                account_id=account.id,
                name=account.name,
                current_balance=balance,
                balance_as_of=as_of,
                balance_is_estimated=estimated,
                credit_limit=credit_limit,
                available_credit=available_credit,
                month_spending=month_spending,
                month_payments=month_payments,
            )
        )
    return out
