"""Net worth math shared by the /net-worth and /dashboard/credit-cards routes.

There's no bank feed, so a "current balance" comes from one of two places:
1. The most recent manually-recorded AccountBalance snapshot, if any.
2. Failing that, for credit-card accounts only, the running sum of that
   account's imported transactions — only meaningful because a card
   typically opens at $0, and only as accurate as "every statement since
   account opening was imported," so it's flagged as estimated rather than
   presented as fact. Every other account type shows "no balance recorded"
   instead of guessing, since there's no such starting point to lean on.
"""

from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Account, AccountBalance, AccountType, Transaction


def _latest_snapshot(
    db: Session, account_id: int, before: date | None = None
) -> AccountBalance | None:
    query = db.query(AccountBalance).filter(AccountBalance.account_id == account_id)
    if before is not None:
        query = query.filter(AccountBalance.as_of_date < before)
    return query.order_by(AccountBalance.as_of_date.desc()).first()


def balance_for_account(
    db: Session, account: Account, before: date | None = None
) -> tuple[float | None, date | None, bool]:
    """Returns (balance, as_of_date, is_estimated). balance is None if there's
    nothing to go on at all (no snapshot and no transactions)."""
    snapshot = _latest_snapshot(db, account.id, before=before)
    if snapshot is not None:
        return float(snapshot.balance), snapshot.as_of_date, False

    if account.account_type != AccountType.credit_card:
        # The running-transaction-total fallback assumes the account started
        # at $0 the moment its earliest imported transaction happened — a
        # reasonable assumption for a freshly-opened credit card, but not for
        # a chequing/savings account you'd had for years before ever
        # uploading a statement. Without a real snapshot, "no balance
        # recorded" is more honest than a number that can be wildly wrong.
        return None, None, False

    query = db.query(func.sum(Transaction.amount)).filter(
        Transaction.account_id == account.id
    )
    if before is not None:
        query = query.filter(Transaction.trans_date < before)
    total = query.scalar()
    if total is not None:
        return float(total), None, True

    return None, None, False
