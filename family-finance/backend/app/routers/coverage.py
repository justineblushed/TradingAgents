"""Statement upload checklist: which account-months have data, which are missing.

A month "has a statement" if the account has at least one transaction dated in
it. The checklist runs from each account's earliest transaction month through
the previous calendar month (the current month's statement usually hasn't been
issued yet, so it isn't counted as missing). Months the user marked as N/A
(no statement exists — card unused, account opened mid-year) show as skipped
and never count as missing.
"""

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Account, AccountType, CoverageSkip, Statement, Transaction
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
    if today.month == 1:
        last_check = date(today.year - 1, 12, 1)
    else:
        last_check = date(today.year, today.month - 1, 1)

    # Track every credit card, plus any other account statements have been
    # uploaded to (chequing etc. once those parsers exist).
    accounts = db.query(Account).order_by(Account.name).all()
    account_ids_with_txns = {
        row[0]
        for row in db.query(Transaction.account_id).distinct()
    }
    tracked = [
        a
        for a in accounts
        if a.account_type == AccountType.credit_card or a.id in account_ids_with_txns
    ]

    skips: dict[int, set[str]] = {}
    for skip in db.query(CoverageSkip).all():
        skips.setdefault(skip.account_id, set()).add(skip.month)

    out: list[AccountCoverage] = []
    total_missing = 0
    for account in tracked:
        last_import: datetime | None = (
            db.query(func.max(Statement.imported_at))
            .filter(Statement.account_id == account.id)
            .scalar()
        )
        days_since = (
            (datetime.utcnow() - last_import).days if last_import is not None else None
        )
        account_skips = skips.get(account.id, set())

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
                    last_imported_at=last_import,
                    days_since_last_import=days_since,
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
            skipped = not covered and month in account_skips
            months.append(
                MonthCoverage(
                    month=month,
                    transaction_count=count,
                    covered=covered,
                    skipped=skipped,
                )
            )
            if not covered and not skipped:
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
                last_imported_at=last_import,
                days_since_last_import=days_since,
            )
        )

    return CoverageSummary(accounts=out, total_missing=total_missing)


class SkipRequest(BaseModel):
    account_id: int
    month: str  # "2026-05"


@router.post("/skip")
def skip_month(payload: SkipRequest, db: Session = Depends(get_db)):
    if db.get(Account, payload.account_id) is None:
        raise HTTPException(404, "Account not found")
    exists = (
        db.query(CoverageSkip)
        .filter(
            CoverageSkip.account_id == payload.account_id,
            CoverageSkip.month == payload.month,
        )
        .first()
    )
    if exists is None:
        db.add(CoverageSkip(account_id=payload.account_id, month=payload.month))
        db.commit()
    return {"ok": True}


@router.delete("/skip")
def unskip_month(account_id: int, month: str, db: Session = Depends(get_db)):
    db.query(CoverageSkip).filter(
        CoverageSkip.account_id == account_id, CoverageSkip.month == month
    ).delete()
    db.commit()
    return {"ok": True}
