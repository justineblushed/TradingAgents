"""Statement upload checklist: which account-months have data, which are missing.

A month "has a statement" if the account has at least one transaction dated in
it. The checklist runs from each account's earliest transaction month through
the previous calendar month (the current month's statement usually hasn't been
issued yet, so it isn't counted as missing).
"""

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Account, AccountType, Transaction
from app.schemas import AccountCoverage, CoverageSummary, MonthCoverage

router = APIRouter(prefix="/coverage", tags=["coverage"])


def _month_range(start: date, end: date) -> list[str]:
    months = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append(f"{year:04d}-{month:02d}")
        month += 1
        if month == 13:
            month = 1
            year += 1
    return months


@router.get("/statements", response_model=CoverageSummary)
def statement_coverage(db: Session = Depends(get_db)):
    today = date.today()
    prev_month_end = today.replace(day=1)  # exclusive upper bound
    # last month to CHECK is the month before the current one
    if today.month == 1:
        last_check = date(today.year - 1, 12, 1)
    else:
        last_check = date(today.year, today.month - 1, 1)

    accounts = (
        db.query(Account).filter(Account.account_type == AccountType.credit_card).all()
    )

    out: list[AccountCoverage] = []
    total_missing = 0
    for account in accounts:
        rows = (
            db.query(Transaction.trans_date)
            .filter(Transaction.account_id == account.id)
            .all()
        )
        if not rows:
            out.append(
                AccountCoverage(
                    account_id=account.id,
                    account_name=account.name,
                    months=[],
                    missing_months=[],
                )
            )
            continue

        counts: dict[str, int] = {}
        earliest = min(r[0] for r in rows)
        for (d,) in rows:
            key = f"{d.year:04d}-{d.month:02d}"
            counts[key] = counts.get(key, 0) + 1

        months = []
        missing = []
        for month in _month_range(earliest.replace(day=1), last_check):
            count = counts.get(month, 0)
            covered = count > 0
            months.append(
                MonthCoverage(month=month, transaction_count=count, covered=covered)
            )
            if not covered:
                missing.append(month)

        # current month shown for information, never counted as missing
        current_key = f"{today.year:04d}-{today.month:02d}"
        if current_key in counts:
            months.append(
                MonthCoverage(
                    month=current_key,
                    transaction_count=counts[current_key],
                    covered=True,
                )
            )

        total_missing += len(missing)
        out.append(
            AccountCoverage(
                account_id=account.id,
                account_name=account.name,
                months=months,
                missing_months=missing,
            )
        )

    return CoverageSummary(accounts=out, total_missing=total_missing)
