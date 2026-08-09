from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dateutil import month_bounds
from app.db import get_db
from app.models import Category, Transaction
from app.schemas import TransactionOut

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=list[TransactionOut])
def list_transactions(month: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Transaction)
    if month:
        start, end = month_bounds(month)
        query = query.filter(Transaction.trans_date >= start, Transaction.trans_date < end)
    rows = query.order_by(Transaction.trans_date).all()
    return [
        TransactionOut(
            id=r.id,
            trans_date=r.trans_date,
            post_date=r.post_date,
            description=r.description,
            amount=float(r.amount),
            category=r.category.name if r.category else None,
        )
        for r in rows
    ]


@router.patch("/{transaction_id}/category")
def set_category(transaction_id: int, category_name: str, db: Session = Depends(get_db)):
    transaction = db.get(Transaction, transaction_id)
    if transaction is None:
        raise HTTPException(404, "Transaction not found")
    category = db.query(Category).filter(Category.name == category_name).first()
    if category is None:
        raise HTTPException(404, "Category not found")
    transaction.category_id = category.id
    db.commit()
    return {"ok": True}
