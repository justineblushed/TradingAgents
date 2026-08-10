"""Tags: a labeling dimension that cuts across categories.

A road trip's groceries stay in Groceries and its fuel stays in Gas &
Parking — the tag is what answers "what did the whole trip cost?". This
keeps the category list from sprouting Travel Food / Travel Gas variants.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import CategoryKind, Tag, Transaction
from app.schemas import TagCreate, TagOut

router = APIRouter(prefix="/tags", tags=["tags"])


def _to_out(tag: Tag) -> TagOut:
    # Spending only: refunds net off, income/transfers ignored, so a trip
    # total reads as "what the trip cost".
    total = 0.0
    for txn in tag.transactions:
        if txn.category and txn.category.kind != CategoryKind.expense:
            continue
        total += float(txn.amount)
    return TagOut(
        id=tag.id,
        name=tag.name,
        transaction_count=len(tag.transactions),
        total_spent=round(total, 2),
    )


@router.get("", response_model=list[TagOut])
def list_tags(db: Session = Depends(get_db)):
    tags = db.query(Tag).order_by(Tag.name).all()
    return [_to_out(t) for t in tags]


@router.post("", response_model=TagOut)
def create_tag(payload: TagCreate, db: Session = Depends(get_db)):
    name = payload.name.strip()
    if not name:
        raise HTTPException(400, "Tag name is required")
    existing = db.query(Tag).filter(Tag.name == name).first()
    if existing is not None:
        return _to_out(existing)
    tag = Tag(name=name)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return _to_out(tag)


@router.delete("/{tag_id}")
def delete_tag(tag_id: int, db: Session = Depends(get_db)):
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(404, "Tag not found")
    # Removing a tag only unlabels transactions; it never deletes them.
    tag.transactions.clear()
    db.delete(tag)
    db.commit()
    return {"ok": True}
