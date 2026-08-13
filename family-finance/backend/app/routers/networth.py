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

    accounts = db.query(Account).order_by(Account.sort_order, Account.name).all()

    assets_total = 0.0
    liabilities_total = 0.0
    # The month-over-month delta only makes sense for accounts that have a
    # genuine data point from *before* this month. An account getting its
    # first-ever balance snapshot this month (e.g. a mortgage entered for
    # the first time) has no fair "last month" to compare against — folding
    # its whole current balance into the delta would show a swing that's
    # really just "this account just started being tracked," not a real
    # month-over-month change. So the delta is computed only over the subset
    # of accounts with both a current and a prior data point.
    delta_current_total = 0.0
    delta_prev_total = 0.0
    accounts_with_history = 0
    accounts_out: list[AccountWithBalance] = []

    for account in accounts:
        balance, as_of, estimated = balance_for_account(db, account)
        prev_balance, _, _ = balance_for_account(db, account, before=first_of_month)

        if balance is not None:
            if account.is_liability:
                liabilities_total += balance
            else:
                assets_total += balance

        if balance is not None and prev_balance is not None:
            accounts_with_history += 1
            signed_current = -balance if account.is_liability else balance
            signed_prev = -prev_balance if account.is_liability else prev_balance
            delta_current_total += signed_current
            delta_prev_total += signed_prev

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
                csv_amount_sign_flipped=account.csv_amount_sign_flipped,
            )
        )

    net_worth = assets_total - liabilities_total
    have_prev_data = accounts_with_history > 0
    net_worth_prev = (net_worth - (delta_current_total - delta_prev_total)) if have_prev_data else None
    delta = (delta_current_total - delta_prev_total) if have_prev_data else None

    return NetWorthSummary(
        assets_total=assets_total,
        liabilities_total=liabilities_total,
        net_worth=net_worth,
        net_worth_prev_month=net_worth_prev,
        delta=delta,
        accounts_with_history=accounts_with_history,
        accounts_total=len(accounts),
        accounts=accounts_out,
    )
