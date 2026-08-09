from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Transaction
from app.schemas import DashboardSummary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def summary(month: str | None = None, db: Session = Depends(get_db)):
    month = month or datetime.utcnow().strftime("%Y-%m")
    year, mon = (int(part) for part in month.split("-"))
    start = f"{year:04d}-{mon:02d}-01"
    end = f"{year + 1:04d}-01-01" if mon == 12 else f"{year:04d}-{mon + 1:02d}-01"

    rows = (
        db.query(Transaction)
        .filter(Transaction.trans_date >= start, Transaction.trans_date < end)
        .all()
    )

    total_credits = -sum(float(r.amount) for r in rows if r.amount < 0)
    total_charges = sum(float(r.amount) for r in rows if r.amount > 0)

    by_category: dict[str, float] = defaultdict(float)
    for r in rows:
        if r.amount > 0:
            name = r.category.name if r.category else "Uncategorized"
            by_category[name] += float(r.amount)

    return DashboardSummary(
        month=month,
        total_charges=total_charges,
        total_credits=total_credits,
        net_change=total_charges - total_credits,
        by_category=dict(by_category),
    )
