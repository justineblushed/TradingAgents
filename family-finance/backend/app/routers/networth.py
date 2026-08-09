from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Account
from app.networth import balance_for_account
from app.schemas import AccountWithBalance, NetWorthSummary

router = APIRouter(prefix="/net-worth", tags=["net-worth"])


@router.get("/summary", response_model=NetWorthSummary)
def summary(db: Session = Depends(get_db)):
    today = date.today()
    first_of_month = today.replace(day=1)

    accounts = db.query(Account).order_by(Account.name).all()

    assets_total = 0.0
    liabilities_total = 0.0
    prev_assets_total = 0.0
    prev_liabilities_total = 0.0
    have_prev_data = False
    accounts_out: list[AccountWithBalance] = []

    for account in accounts:
        balance, as_of, estimated = balance_for_account(db, account)
        prev_balance, _, _ = balance_for_account(db, account, before=first_of_month)

        if balance is not None:
            if account.is_liability:
                liabilities_total += balance
            else:
                assets_total += balance

        if prev_balance is not None:
            have_prev_data = True
            if account.is_liability:
                prev_liabilities_total += prev_balance
            else:
                prev_assets_total += prev_balance

        accounts_out.append(
            AccountWithBalance(
                id=account.id,
                name=account.name,
                account_type=account.account_type.value,
                is_liability=account.is_liability,
                credit_limit=float(account.credit_limit) if account.credit_limit else None,
                current_balance=balance,
                balance_as_of=as_of,
                balance_is_estimated=estimated,
            )
        )

    net_worth = assets_total - liabilities_total
    net_worth_prev = (
        prev_assets_total - prev_liabilities_total if have_prev_data else None
    )
    delta = net_worth - net_worth_prev if net_worth_prev is not None else None

    return NetWorthSummary(
        assets_total=assets_total,
        liabilities_total=liabilities_total,
        net_worth=net_worth,
        net_worth_prev_month=net_worth_prev,
        delta=delta,
        accounts=accounts_out,
    )
