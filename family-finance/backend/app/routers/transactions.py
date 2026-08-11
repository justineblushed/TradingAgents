from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.dateutil import month_bounds
from app.db import get_db
from app.models import Category, CategorySource, Tag, Transaction
from app.schemas import TransactionOut, TransactionTagsUpdate

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _to_out(r: Transaction) -> TransactionOut:
    return TransactionOut(
        id=r.id,
        trans_date=r.trans_date,
        post_date=r.post_date,
        description=r.description,
        amount=float(r.amount),
        category=r.category.name if r.category else None,
        tags=sorted(t.name for t in r.tags),
    )


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    month: str | None = None,
    tag: str | None = None,
    category: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Transaction).options(
        joinedload(Transaction.category), joinedload(Transaction.tags)
    )
    if month:
        start, end = month_bounds(month)
        query = query.filter(Transaction.trans_date >= start, Transaction.trans_date < end)
    if tag:
        query = query.filter(Transaction.tags.any(Tag.name == tag))
    if category == "Uncategorized":
        query = query.filter(Transaction.category_id.is_(None))
    elif category:
        record = db.query(Category).filter(Category.name == category).first()
        if record is None:
            raise HTTPException(404, f"No category named {category!r}")
        query = query.filter(Transaction.category_id == record.id)
    rows = query.order_by(Transaction.trans_date).all()
    return [_to_out(r) for r in rows]


@router.patch("/{transaction_id}/category")
def set_category(transaction_id: int, category_name: str, db: Session = Depends(get_db)):
    transaction = db.get(Transaction, transaction_id)
    if transaction is None:
        raise HTTPException(404, "Transaction not found")
    category = db.query(Category).filter(Category.name == category_name).first()
    if category is None:
        raise HTTPException(404, "Category not found")
    transaction.category_id = category.id
    # Choosing a category by hand pins it: a later retroactive rule run will
    # skip this row rather than overwrite the correction.
    transaction.category_source = CategorySource.manual
    db.commit()
    return {"ok": True}


@router.put("/{transaction_id}/tags", response_model=TransactionOut)
def set_tags(
    transaction_id: int, payload: TransactionTagsUpdate, db: Session = Depends(get_db)
):
    transaction = db.get(Transaction, transaction_id)
    if transaction is None:
        raise HTTPException(404, "Transaction not found")

    wanted = []
    seen: set[str] = set()
    for raw in payload.tags:
        name = raw.strip()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        tag = db.query(Tag).filter(Tag.name == name).first()
        if tag is None:
            # Tagging a transaction with a new label creates it on the fly —
            # no separate "create the tag first" step.
            tag = Tag(name=name)
            db.add(tag)
            db.flush()
        wanted.append(tag)

    transaction.tags = wanted
    db.commit()
    db.refresh(transaction)
    return _to_out(transaction)
