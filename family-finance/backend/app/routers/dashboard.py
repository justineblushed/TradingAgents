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
    AreaToWatch,
    BudgetVariance,
    CostTypeSlice,
    CreditCardSummary,
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
# Only spending that both moves month to month AND is realistically within the
# household's control can contribute to the adjustable estimate. A car repair is
# variable but not a choice; a mortgage is neither.
_ADJUSTABLE_COST_TYPES = {CostType.variable, CostType.recurring}
_ADJUSTABLE_CONTROL = {Controllability.high, Controllability.very_high}
# Below this, "typical" is an average of too few months to mean anything.
_MIN_HISTORY_MONTHS = 2


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

    # Each category's own recent history — the honest baseline for "is this
    # month unusual?". Excludes the month being viewed.
    history_months = [m for m in recent_complete_months(db, limit=4) if m < month][:3]
    history: dict[str, list[float]] = defaultdict(list)
    for m in history_months:
        for name, amount in month_flows(db, m)[2].items():
            history[name].append(amount)

    budget_variances: list[BudgetVariance] = []
    over_budget_total = 0.0
    areas: list[AreaToWatch] = []
    adjustable_low = 0.0
    adjustable_high = 0.0
    have_adjustable = False

    for category in db.query(Category).filter(Category.kind == CategoryKind.expense).all():
        spent = spent_by_category.get(category.name, 0.0)
        if spent <= 0:
            continue

        # 1. Budget variance — a plain fact about this month vs. the target.
        if category.monthly_budget is not None:
            budget = float(category.monthly_budget)
            if spent > budget:
                over = spent - budget
                over_budget_total += over
                budget_variances.append(
                    BudgetVariance(
                        category=category.name,
                        budget=round(budget, 2),
                        spent=round(spent, 2),
                        over=round(over, 2),
                    )
                )

        # 2. Areas to watch — high against this category's own normal.
        values = history.get(category.name, [])
        if len(values) < _MIN_HISTORY_MONTHS:
            continue
        typical = sum(values) / len(values)
        above = spent - typical
        if above <= 0 or typical <= 0:
            continue
        adjustable = (
            category.cost_type in _ADJUSTABLE_COST_TYPES
            and category.controllability in _ADJUSTABLE_CONTROL
        )
        areas.append(
            AreaToWatch(
                category=category.name,
                group_name=category.group_name or "",
                cost_type=category.cost_type.value,
                controllability=category.controllability.value,
                spent=round(spent, 2),
                typical=round(typical, 2),
                above_typical=round(above, 2),
                percent_above=round(above / typical * 100, 0),
                months_of_history=len(values),
                highlight=adjustable,
            )
        )

        # 3. Adjustable range, bounded by what this household has actually
        # done before: low = back to its own typical, high = match its best
        # recent month. Never an open-ended promise.
        if adjustable:
            have_adjustable = True
            adjustable_low += above
            adjustable_high += spent - min(values)

    budget_variances.sort(key=lambda b: -b.over)
    areas.sort(key=lambda a: -a.above_typical)

    return SpendingControl(
        month=month,
        total_spending=round(total_spending, 2),
        by_cost_type=slices,
        locked_amount=round(locked_amount, 2),
        over_budget_total=round(over_budget_total, 2),
        budget_variances=budget_variances,
        areas_to_watch=areas,
        adjustable_low=round(adjustable_low, 2) if have_adjustable else None,
        adjustable_high=round(adjustable_high, 2) if have_adjustable else None,
        adjustable_months_of_history=len(history_months),
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
