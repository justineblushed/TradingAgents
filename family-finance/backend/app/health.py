"""Financial health metrics.

The score is deliberately a *summary*, not the product: each metric carries
its own status and detail line, and metrics with no underlying data are
reported as "no data" and excluded from the score entirely (weights are
renormalized) rather than silently dragging it down.

Flow metrics (income/spending) use the most recent *complete* calendar month
that has transactions — the current month is partial and would skew ratios.
Averages use up to the last 3 complete months with data.
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session, joinedload

from app.models import Account, AccountType, Category, CategoryKind, Transaction
from app.networth import balance_for_account

LIQUID_TYPES = {AccountType.cash, AccountType.chequing, AccountType.savings}
INVESTMENT_TYPES = {
    AccountType.investment,
    AccountType.tfsa,
    AccountType.rrsp,
    AccountType.resp,
}

# Metric weights (renormalized over the metrics that have data).
WEIGHTS = {
    "emergency_fund": 25,
    "savings_rate": 25,
    "housing_cost": 15,
    "budget": 15,
    "debt_trend": 10,
    "investments": 10,
}


@dataclass
class Metric:
    key: str
    label: str
    status: str  # "good" | "warn" | "bad" | "none"
    display_value: str
    detail: str
    score: float | None  # None = no data, excluded from overall score


def _month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _prev_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def _recent_complete_months(db: Session, limit: int = 3) -> list[str]:
    """Up to `limit` most recent complete calendar months that have any
    transactions, newest first."""
    today = date.today()
    months_with_data = {
        _month_key(row[0]) for row in db.query(Transaction.trans_date).all()
    }
    out: list[str] = []
    year, month = _prev_month(today.year, today.month)
    # Walk back at most 24 months looking for data.
    for _ in range(24):
        key = f"{year:04d}-{month:02d}"
        if key in months_with_data:
            out.append(key)
            if len(out) == limit:
                break
        year, month = _prev_month(year, month)
    return out


def _month_flows(
    db: Session, month: str
) -> tuple[float, float, dict[str, float], dict[str, float]]:
    """(spending, income, spending_by_category, spending_by_group) for a month.

    Transfers excluded; refunds net against their expense category — the same
    rules as the dashboard, so the two never disagree."""
    start = f"{month}-01"
    year, mon = (int(p) for p in month.split("-"))
    end = f"{year + 1:04d}-01-01" if mon == 12 else f"{year:04d}-{mon + 1:02d}-01"
    rows = (
        db.query(Transaction)
        .options(joinedload(Transaction.category))
        .filter(Transaction.trans_date >= start, Transaction.trans_date < end)
        .all()
    )
    rows = [
        r for r in rows if not (r.category and r.category.kind == CategoryKind.transfer)
    ]
    spending = 0.0
    income = 0.0
    by_cat: dict[str, float] = {}
    by_group: dict[str, float] = {}
    for r in rows:
        amount = float(r.amount)
        kind = r.category.kind if r.category else None
        if kind == CategoryKind.expense or (kind is None and amount > 0):
            spending += amount
            name = r.category.name if r.category else "Uncategorized"
            group = (r.category.group_name or "Other") if r.category else "Uncategorized"
            by_cat[name] = by_cat.get(name, 0.0) + amount
            by_group[group] = by_group.get(group, 0.0) + amount
        else:
            income += -amount
    return spending, income, by_cat, by_group


def compute_health(db: Session) -> dict:
    months = _recent_complete_months(db)
    ref_month = months[0] if months else None

    flows = {m: _month_flows(db, m) for m in months}
    avg_spending = (
        sum(f[0] for f in flows.values()) / len(flows) if flows else None
    )

    accounts = db.query(Account).all()
    metrics: list[Metric] = []

    # --- Emergency fund ---
    liquid_total = 0.0
    have_liquid_data = False
    for a in accounts:
        if a.account_type in LIQUID_TYPES:
            balance, _, estimated = balance_for_account(db, a)
            if balance is not None and not estimated:
                liquid_total += balance
                have_liquid_data = True
    if have_liquid_data and avg_spending:
        months_covered = liquid_total / avg_spending
        status = "good" if months_covered >= 3 else "warn" if months_covered >= 1 else "bad"
        metrics.append(
            Metric(
                "emergency_fund",
                "Emergency fund",
                status,
                f"{months_covered:.1f} months",
                f"Liquid savings cover {months_covered:.1f} months of average spending (target: 3–6).",
                min(100.0, months_covered / 6 * 100),
            )
        )
    else:
        metrics.append(
            Metric(
                "emergency_fund",
                "Emergency fund",
                "none",
                "No data",
                "Record balances for cash/chequing/savings accounts on the Net Worth page.",
                None,
            )
        )

    # --- Savings rate ---
    if ref_month and flows[ref_month][1] > 0:
        spending, income, _, _ = flows[ref_month]
        rate = (income - spending) / income
        pct = rate * 100
        status = "good" if pct >= 15 else "warn" if pct >= 5 else "bad"
        metrics.append(
            Metric(
                "savings_rate",
                "Savings rate",
                status,
                f"{pct:.0f}%",
                f"In {ref_month} you kept {pct:.0f}% of income after spending (target: 20%+).",
                max(0.0, min(100.0, rate / 0.20 * 100)),
            )
        )
    else:
        metrics.append(
            Metric(
                "savings_rate",
                "Savings rate",
                "none",
                "No data",
                "Needs a complete month with income transactions (e.g. payroll deposits).",
                None,
            )
        )

    # --- Housing cost ---
    if ref_month and flows[ref_month][1] > 0:
        _, income, _, by_group = flows[ref_month]
        housing = by_group.get("Housing", 0.0)
        pct = housing / income * 100
        status = "good" if pct <= 30 else "warn" if pct <= 40 else "bad"
        if pct <= 30:
            score = 100.0
        elif pct <= 40:
            score = 100 - (pct - 30) * 6  # 30%→100 down to 40%→40
        else:
            score = 20.0
        metrics.append(
            Metric(
                "housing_cost",
                "Housing cost",
                status,
                f"{pct:.0f}%",
                f"The Housing group took {pct:.0f}% of {ref_month} income (guideline: ≤30%).",
                score,
            )
        )
    else:
        metrics.append(
            Metric(
                "housing_cost",
                "Housing cost",
                "none",
                "No data",
                "Needs a complete month with income transactions.",
                None,
            )
        )

    # --- Spending vs budget ---
    budgeted = (
        db.query(Category)
        .filter(Category.monthly_budget.isnot(None), Category.kind == CategoryKind.expense)
        .all()
    )
    if budgeted and ref_month:
        _, _, by_cat, _ = flows[ref_month]
        over_total = 0.0
        budget_total = 0.0
        over_count = 0
        for c in budgeted:
            budget = float(c.monthly_budget)
            budget_total += budget
            spent = by_cat.get(c.name, 0.0)
            if spent > budget:
                over_total += spent - budget
                over_count += 1
        if over_count == 0:
            metrics.append(
                Metric(
                    "budget",
                    "Spending",
                    "good",
                    "Within budget",
                    f"All {len(budgeted)} budgeted categories stayed under target in {ref_month}.",
                    100.0,
                )
            )
        else:
            overshoot_pct = over_total / budget_total * 100 if budget_total else 0
            status = "warn" if overshoot_pct <= 20 else "bad"
            metrics.append(
                Metric(
                    "budget",
                    "Spending",
                    status,
                    f"{over_count} over budget",
                    f"{over_count} of {len(budgeted)} budgeted categories went over in {ref_month} (${over_total:,.0f} total).",
                    max(20.0, 100 - overshoot_pct * 2),
                )
            )
    else:
        metrics.append(
            Metric(
                "budget",
                "Spending",
                "none",
                "No targets set",
                "Set monthly targets on the Categories page to track budget adherence.",
                None,
            )
        )

    # --- Debt trend ---
    first_of_month = date.today().replace(day=1)
    debt_now = 0.0
    debt_prev = 0.0
    have_debt_data = False
    for a in accounts:
        if a.is_liability:
            now_bal, _, now_est = balance_for_account(db, a)
            prev_bal, _, prev_est = balance_for_account(db, a, before=first_of_month)
            if now_bal is not None and prev_bal is not None and not now_est and not prev_est:
                debt_now += now_bal
                debt_prev += prev_bal
                have_debt_data = True
    if have_debt_data:
        delta = debt_now - debt_prev
        if delta <= 0:
            metrics.append(
                Metric(
                    "debt_trend",
                    "Debt payment",
                    "good",
                    "On track",
                    f"Total liabilities down ${-delta:,.0f} vs last month."
                    if delta < 0
                    else "Total liabilities unchanged vs last month.",
                    100.0 if delta < 0 else 70.0,
                )
            )
        else:
            metrics.append(
                Metric(
                    "debt_trend",
                    "Debt payment",
                    "warn",
                    "Growing",
                    f"Total liabilities up ${delta:,.0f} vs last month.",
                    40.0,
                )
            )
    else:
        metrics.append(
            Metric(
                "debt_trend",
                "Debt payment",
                "none",
                "No data",
                "Record liability balances (credit cards, mortgage) across two months on the Net Worth page.",
                None,
            )
        )

    # --- Investments ---
    inv_now = 0.0
    inv_prev = 0.0
    have_inv_data = False
    for a in accounts:
        if a.account_type in INVESTMENT_TYPES:
            now_bal, _, now_est = balance_for_account(db, a)
            prev_bal, _, prev_est = balance_for_account(db, a, before=first_of_month)
            if now_bal is not None and not now_est:
                have_inv_data = True
                inv_now += now_bal
                if prev_bal is not None and not prev_est:
                    inv_prev += prev_bal
    if have_inv_data:
        if inv_prev > 0:
            delta = inv_now - inv_prev
            if delta > 0:
                metrics.append(
                    Metric(
                        "investments", "Investments", "good", "Growing",
                        f"Investment accounts up ${delta:,.0f} vs last month.", 100.0,
                    )
                )
            elif delta == 0:
                metrics.append(
                    Metric(
                        "investments", "Investments", "warn", "Flat",
                        "Investment balances unchanged vs last month.", 60.0,
                    )
                )
            else:
                metrics.append(
                    Metric(
                        "investments", "Investments", "warn", "Down",
                        f"Investment accounts down ${-delta:,.0f} vs last month.", 50.0,
                    )
                )
        else:
            metrics.append(
                Metric(
                    "investments", "Investments", "good", f"${inv_now:,.0f}",
                    "Balances recorded — month-over-month trend appears after next month's update.",
                    80.0,
                )
            )
    else:
        metrics.append(
            Metric(
                "investments",
                "Investments",
                "none",
                "No data",
                "Record balances for TFSA/RRSP/RESP/investment accounts on the Net Worth page.",
                None,
            )
        )

    # --- Overall score (renormalized over metrics that have data) ---
    scored = [m for m in metrics if m.score is not None]
    if scored:
        total_weight = sum(WEIGHTS[m.key] for m in scored)
        score = round(sum(m.score * WEIGHTS[m.key] for m in scored) / total_weight)
    else:
        score = None

    if score is None:
        band = "NOT ENOUGH DATA"
    elif score >= 85:
        band = "EXCELLENT"
    elif score >= 70:
        band = "GOOD"
    elif score >= 50:
        band = "FAIR"
    else:
        band = "NEEDS ATTENTION"

    # --- Biggest opportunity ---
    opportunity = None
    if ref_month:
        _, _, by_cat, _ = flows[ref_month]
        budgets = {c.name: float(c.monthly_budget) for c in budgeted}
        # historical average per category over the older months (excluding ref)
        older = months[1:]
        hist: dict[str, list[float]] = {}
        for m in older:
            for name, amount in flows[m][2].items():
                hist.setdefault(name, []).append(amount)

        best = None
        for name, spent in by_cat.items():
            if name in budgets:
                target, basis = budgets[name], "target"
            elif name in hist:
                target, basis = sum(hist[name]) / len(hist[name]), "typical spending"
            else:
                continue
            over = spent - target
            if over > 0 and (best is None or over > best[1]):
                best = (name, over, basis)
        if best:
            name, over, basis = best
            opportunity = {
                "category": name,
                "over_amount": round(over, 2),
                "annual_saving": round(over * 12, 2),
                "basis": basis,
                "month": ref_month,
            }

    return {
        "score": score,
        "band": band,
        "reference_month": ref_month,
        "metrics": [
            {
                "key": m.key,
                "label": m.label,
                "status": m.status,
                "display_value": m.display_value,
                "detail": m.detail,
            }
            for m in metrics
        ],
        "opportunity": opportunity,
    }
