from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.dateutil import month_bounds
from app.db import get_db
from app.health import month_flows, recent_complete_months
from app.models import (
    Account,
    AccountType,
    Category,
    CategoryKind,
    Controllability,
    CostType,
    Transaction,
)
from app.networth import balance_for_account
from app.schemas import (
    CostTypeSlice,
    CreditCardSummary,
    CutCandidate,
    DashboardSummary,
    SpendingControl,
)

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

    # Spending is the NET of expense-kind transactions: a merchant refund
    # filed under Groceries offsets Groceries rather than counting as income.
    # Income is the net of income-kind transactions. Uncategorized rows fall
    # back to sign: positive = spending, negative = income.
    total_spending = 0.0
    total_income = 0.0
    by_category: dict[str, float] = defaultdict(float)
    by_group: dict[str, float] = defaultdict(float)

    for r in rows:
        amount = float(r.amount)
        kind = r.category.kind if r.category else None
        is_spending = kind == CategoryKind.expense or (kind is None and amount > 0)
        if is_spending:
            total_spending += amount
            name = r.category.name if r.category else "Uncategorized"
            group = (r.category.group_name or "Other") if r.category else "Uncategorized"
            by_category[name] += amount
            by_group[group] += amount
        else:
            total_income += -amount

    return DashboardSummary(
        month=month,
        total_spending=total_spending,
        total_income=total_income,
        net_cash_flow=total_income - total_spending,
        by_category=dict(by_category),
        by_group=dict(by_group),
    )


_COST_TYPE_LABELS = {
    CostType.fixed: "Fixed",
    CostType.recurring: "Recurring",
    CostType.variable: "Variable",
    CostType.irregular: "Irregular",
}
_COST_TYPE_ORDER = [CostType.fixed, CostType.recurring, CostType.variable, CostType.irregular]
# Only these are counted toward "potential savings" — a variable-but-unavoidable
# cost (car repair, medical) shouldn't be presented as money you can choose to keep.
_CUTTABLE = {Controllability.high, Controllability.very_high}


@router.get("/spending-control", response_model=SpendingControl)
def spending_control(month: str | None = None, db: Session = Depends(get_db)):
    month = month or _current_month()
    start, end = month_bounds(month)

    rows = (
        db.query(Transaction)
        .options(joinedload(Transaction.category))
        .filter(Transaction.trans_date >= start, Transaction.trans_date < end)
        .all()
    )
    rows = [r for r in rows if not (r.category and r.category.kind == CategoryKind.transfer)]

    spent_by_category: dict[str, float] = defaultdict(float)
    by_cost: dict[CostType, float] = defaultdict(float)
    total_spending = 0.0
    for r in rows:
        amount = float(r.amount)
        kind = r.category.kind if r.category else None
        if kind != CategoryKind.expense and not (kind is None and amount > 0):
            continue
        total_spending += amount
        if r.category:
            spent_by_category[r.category.name] += amount
            by_cost[r.category.cost_type] += amount
        else:
            # Uncategorized spending is unclassifiable; treat as variable so
            # it shows up as adjustable rather than silently "locked".
            by_cost[CostType.variable] += amount

    slices = [
        CostTypeSlice(
            cost_type=ct.value,
            label=_COST_TYPE_LABELS[ct],
            amount=round(by_cost.get(ct, 0.0), 2),
            percent=round(by_cost.get(ct, 0.0) / total_spending * 100, 1)
            if total_spending
            else 0.0,
        )
        for ct in _COST_TYPE_ORDER
        if by_cost.get(ct, 0.0) > 0
    ]
    locked_amount = by_cost.get(CostType.fixed, 0.0) + by_cost.get(CostType.irregular, 0.0)

    # Historical baseline for categories with no explicit budget: their
    # average in the complete months before this one.
    history_months = [m for m in recent_complete_months(db, limit=4) if m < month][:3]
    history: dict[str, list[float]] = defaultdict(list)
    for m in history_months:
        for name, amount in month_flows(db, m)[2].items():
            history[name].append(amount)

    candidates: list[CutCandidate] = []
    potential_savings = 0.0
    for category in db.query(Category).filter(Category.kind == CategoryKind.expense).all():
        spent = spent_by_category.get(category.name, 0.0)
        if spent <= 0:
            continue
        if category.monthly_budget is not None:
            reference, basis = float(category.monthly_budget), "budget"
        elif history.get(category.name):
            values = history[category.name]
            reference, basis = sum(values) / len(values), "typical spending"
        else:
            continue
        over = spent - reference
        if over <= 0:
            continue
        candidates.append(
            CutCandidate(
                category=category.name,
                group_name=category.group_name or "",
                cost_type=category.cost_type.value,
                controllability=category.controllability.value,
                spent=round(spent, 2),
                reference=round(reference, 2),
                over=round(over, 2),
                basis=basis,
            )
        )
        if category.controllability in _CUTTABLE:
            potential_savings += over

    control_rank = {
        Controllability.very_high.value: 0,
        Controllability.high.value: 1,
        Controllability.medium.value: 2,
        Controllability.low.value: 3,
    }
    candidates.sort(key=lambda c: (control_rank.get(c.controllability, 9), -c.over))

    return SpendingControl(
        month=month,
        total_spending=round(total_spending, 2),
        by_cost_type=slices,
        locked_amount=round(locked_amount, 2),
        cut_candidates=candidates,
        potential_savings=round(potential_savings, 2),
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
