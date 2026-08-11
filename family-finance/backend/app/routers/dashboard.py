from collections import defaultdict
from datetime import date as date_type, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
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
    PayStub,
    Transaction,
)
from app.networth import balance_for_account
from app.recurring import detect_recurring, next_payday
from app.schemas import (
    AreaToWatch,
    BudgetVariance,
    CategoryDetail,
    CategoryMonthPoint,
    CostTypeSlice,
    CreditCardSummary,
    DashboardSummary,
    NextPayday,
    SpendingControl,
    TransactionOut,
    UpcomingBill,
    UpcomingSummary,
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


# How much history to read when looking for repeating charges. Long enough to
# catch a quarterly bill three times over, short enough that a subscription
# cancelled two years ago doesn't resurface.
_RECURRING_LOOKBACK_DAYS = 800


@router.get("/upcoming", response_model=UpcomingSummary)
def upcoming(
    horizon_days: int = 30,
    today: date_type | None = None,
    db: Session = Depends(get_db),
):
    """What's coming: next payday, and the bills history says are due.

    Nothing here was entered as a schedule — both halves are inferred, the
    payday from pay stub cadence and the bills from repeating charges. Each
    carries the evidence it came from so the household can tell a real
    obligation from a coincidence.
    """
    today = today or date_type.today()
    horizon_days = max(1, min(horizon_days, 120))
    horizon = today + timedelta(days=horizon_days)

    # --- next payday ---------------------------------------------------
    payday: NextPayday | None = None
    payday_hint = ""
    stubs = db.query(PayStub).order_by(PayStub.pay_date).all()
    projected = next_payday([s.pay_date for s in stubs], today)
    if projected is not None:
        pay_date, basis, _gap = projected
        # Expect what the recent stubs actually paid, not an all-time average
        # — a raise or a change in hours shouldn't be diluted by last year.
        recent = [float(s.net_pay) for s in stubs[-3:] if float(s.net_pay) > 0]
        by_employer = [s.employer for s in stubs if s.employer]
        payday = NextPayday(
            pay_date=pay_date,
            days_away=(pay_date - today).days,
            expected_net=round(sum(recent) / len(recent), 2) if recent else None,
            employer=by_employer[-1] if by_employer else "",
            basis=basis,
        )
    elif len(stubs) == 1:
        payday_hint = (
            "One pay stub so far — add the next one and the pay rhythm can "
            "be worked out."
        )
    else:
        payday_hint = "Add pay stubs on the Payroll page to project your next payday."

    # --- upcoming bills --------------------------------------------------
    since = today - timedelta(days=_RECURRING_LOOKBACK_DAYS)
    rows = (
        db.query(Transaction)
        .options(joinedload(Transaction.category), joinedload(Transaction.account))
        .filter(Transaction.trans_date >= since)
        .all()
    )
    series = detect_recurring(
        [
            {
                "description": r.description,
                "amount": float(r.amount),
                "trans_date": r.trans_date,
                "account_id": r.account_id,
                "account_name": r.account.name if r.account else "",
                "category": r.category.name if r.category else None,
                "kind": r.category.kind.value if r.category else "expense",
            }
            for r in rows
        ],
        today=today,
    )

    bills: list[UpcomingBill] = []
    for s in series:
        # Income has its own card above; a refund series isn't a bill either.
        if s.kind == "income" or s.typical_amount <= 0:
            continue
        if s.next_date > horizon:
            continue
        bills.append(
            UpcomingBill(
                description=s.description,
                category=s.category,
                account_name=s.account_name,
                expected_date=s.next_date,
                days_away=(s.next_date - today).days,
                expected_amount=s.typical_amount,
                amount_low=s.amount_low,
                amount_high=s.amount_high,
                amount_varies=s.amount_varies,
                cadence=s.cadence,
                occurrences=s.occurrences,
                basis=s.basis,
                overdue=s.next_date < today,
            )
        )

    if not bills:
        bills_hint = (
            "No repeating charges found yet. A bill shows up here once it has "
            "been imported at least three times on a steady rhythm."
            if rows
            else "Import some statements and repeating bills will be spotted here."
        )
    else:
        bills_hint = ""

    return UpcomingSummary(
        as_of=today,
        horizon_days=horizon_days,
        next_payday=payday,
        payday_hint=payday_hint,
        bills=bills,
        bills_total=round(sum(b.expected_amount for b in bills), 2),
        bills_hint=bills_hint,
    )


# How many months of history the drill-down shows. A year reads as a season
# cycle (heating, holidays) without the chart turning into a smear.
_DETAIL_HISTORY_MONTHS = 12


def _shift_month(month: str, delta: int) -> str:
    year, mon = (int(p) for p in month.split("-"))
    index = year * 12 + (mon - 1) + delta
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


@router.get("/category-detail", response_model=CategoryDetail)
def category_detail(
    category: str, month: str | None = None, db: Session = Depends(get_db)
):
    """Everything about one category in one month, plus a year of context.

    The total nets refunds against the category exactly as /summary does,
    so drilling into a bar never shows a different number than the bar
    itself. "Uncategorized" is a real destination here — it's where the
    work is — even though it isn't a row in the categories table.
    """
    month = month or _current_month()
    is_uncategorized = category == "Uncategorized"

    record = (
        None
        if is_uncategorized
        else db.query(Category).filter(Category.name == category).first()
    )
    if record is None and not is_uncategorized:
        raise HTTPException(404, f"No category named {category!r}")

    start, end = month_bounds(month)
    query = (
        db.query(Transaction)
        .options(joinedload(Transaction.category), joinedload(Transaction.tags))
        .filter(Transaction.trans_date >= start, Transaction.trans_date < end)
    )
    if is_uncategorized:
        query = query.filter(Transaction.category_id.is_(None))
    else:
        query = query.filter(Transaction.category_id == record.id)
    rows = query.order_by(Transaction.trans_date).all()

    total = round(sum(float(r.amount) for r in rows), 2)
    # Income reads more naturally as a positive number; expenses are already
    # positive in this app's convention.
    if record is not None and record.kind == CategoryKind.income:
        total = -total

    history: list[CategoryMonthPoint] = []
    for offset in range(_DETAIL_HISTORY_MONTHS - 1, -1, -1):
        m = _shift_month(month, -offset)
        m_start, m_end = month_bounds(m)
        m_query = db.query(Transaction).filter(
            Transaction.trans_date >= m_start, Transaction.trans_date < m_end
        )
        if is_uncategorized:
            m_query = m_query.filter(Transaction.category_id.is_(None))
        else:
            m_query = m_query.filter(Transaction.category_id == record.id)
        m_total = sum(float(r.amount) for r in m_query.all())
        if record is not None and record.kind == CategoryKind.income:
            m_total = -m_total
        history.append(
            CategoryMonthPoint(month=m, total=round(m_total, 2), is_current=(m == month))
        )

    # "Typical" excludes the month on screen and any month with nothing in it
    # — averaging in months before the account existed would drag it down and
    # make every real month look like an overspend.
    others = [p.total for p in history if not p.is_current and p.total != 0]
    average = round(sum(others) / len(others), 2) if others else None

    budget = (
        float(record.monthly_budget)
        if record is not None and record.monthly_budget is not None
        else None
    )

    return CategoryDetail(
        category=category,
        kind=record.kind.value if record is not None else "expense",
        group_name=(record.group_name or "") if record is not None else "",
        color=(record.color or "") if record is not None else "#94a3b8",
        emoji=(record.emoji or "") if record is not None else "❓",
        month=month,
        total=total,
        transaction_count=len(rows),
        monthly_budget=budget,
        over_budget=round(total - budget, 2) if budget is not None and total > budget else None,
        average_of_history=average,
        history=history,
        transactions=[
            TransactionOut(
                id=r.id,
                trans_date=r.trans_date,
                post_date=r.post_date,
                description=r.description,
                amount=float(r.amount),
                category=r.category.name if r.category else None,
                tags=sorted(t.name for t in r.tags),
            )
            for r in rows
        ],
    )
