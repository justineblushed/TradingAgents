from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.dateutil import month_bounds
from app.db import get_db
from app.models import Category, CategoryKind, CategorySource, Tag, Transaction
from app.schemas import (
    SignIssue,
    SignIssueFixRequest,
    SignIssueFixResult,
    TransactionOut,
    TransactionTagsUpdate,
)

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


@router.get("/sign-issues", response_model=list[SignIssue])
def list_sign_issues(db: Session = Depends(get_db)):
    """Income-kind transactions stored with a positive amount.

    This app's convention is negative = money in; every place that
    reports income (dashboard, cash flow, category drill-down) negates a
    category's raw total to display it as a positive number. A
    transaction stored the wrong way round doesn't just look odd on its
    own — it drags every one of those totals toward zero or negative,
    usually because it was imported before a CSV's own sign convention
    was reconciled against this app's. This finds every such row so it
    can be corrected explicitly rather than guessed at.
    """
    rows = (
        db.query(Transaction)
        .join(Category)
        .options(joinedload(Transaction.category), joinedload(Transaction.account))
        .filter(Category.kind == CategoryKind.income, Transaction.amount > 0)
        .order_by(Transaction.trans_date.desc())
        .all()
    )
    return [
        SignIssue(
            id=r.id,
            trans_date=r.trans_date,
            description=r.description,
            amount=float(r.amount),
            category=r.category.name,
            account_name=r.account.name if r.account else "",
        )
        for r in rows
    ]


@router.post("/sign-issues/fix", response_model=SignIssueFixResult)
def fix_sign_issues(payload: SignIssueFixRequest, db: Session = Depends(get_db)):
    if not payload.transaction_ids:
        raise HTTPException(400, "No transactions selected")
    fixed = 0
    already_ok = 0
    for transaction_id in payload.transaction_ids:
        txn = db.get(Transaction, transaction_id)
        if txn is None:
            continue
        # Re-check rather than trust the caller's list blindly — something
        # else may have already fixed or recategorized this row since it
        # was listed, and flipping a now-correct row would just reintroduce
        # the bug the other way.
        if txn.category and txn.category.kind == CategoryKind.income and txn.amount > 0:
            txn.amount = -txn.amount
            fixed += 1
        else:
            already_ok += 1
    db.commit()
    return SignIssueFixResult(fixed=fixed, already_ok=already_ok)
