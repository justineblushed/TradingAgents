from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from app.dateutil import month_bounds
from app.db import get_db
from app.models import Category, CategoryKind, CategorySource, Tag, Transaction
from app.schemas import (
    DuplicateFixRequest,
    DuplicateFixResult,
    DuplicateGroup,
    DuplicateTransactionCopy,
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
    kind: str | None = None,
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
    if kind == "expense":
        # Matches the is_spending logic used everywhere else (dashboard
        # summary, Sankey): an uncategorized row with a positive amount
        # reads as spending too, same as this app's own sign convention.
        query = query.filter(
            or_(
                Transaction.category.has(Category.kind == CategoryKind.expense),
                and_(Transaction.category_id.is_(None), Transaction.amount > 0),
            )
        )
    elif kind == "income":
        query = query.filter(
            or_(
                Transaction.category.has(Category.kind == CategoryKind.income),
                and_(Transaction.category_id.is_(None), Transaction.amount < 0),
            )
        )
    elif kind is not None:
        raise HTTPException(400, "kind must be 'expense' or 'income'")
    rows = query.order_by(Transaction.trans_date).all()
    return [_to_out(r) for r in rows]


@router.delete("/{transaction_id}")
def delete_transaction(transaction_id: int, db: Session = Depends(get_db)):
    transaction = db.get(Transaction, transaction_id)
    if transaction is None:
        raise HTTPException(404, "Transaction not found")
    db.delete(transaction)
    db.commit()
    return {"ok": True}


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


def _is_sign_issue(txn: Transaction) -> str | None:
    """Returns the issue direction if txn's amount sign contradicts its
    category's kind, else None. Kept as a single source of truth so the
    list endpoint and the fix endpoint's re-check can never drift apart."""
    if txn.category is None:
        return None
    if txn.category.kind == CategoryKind.income and txn.amount > 0:
        return "income_positive"
    if txn.category.kind == CategoryKind.expense and txn.amount < 0:
        return "expense_negative"
    return None


@router.get("/sign-issues", response_model=list[SignIssue])
def list_sign_issues(db: Session = Depends(get_db)):
    """Transactions whose amount sign contradicts their category's kind.

    This app's convention is negative = money in, positive = money out;
    every place that reports income or spending (dashboard, cash flow,
    category drill-down) relies on that. Two directions, at two
    different confidence levels — see SignIssue's docstring. Both are
    usually left over from a CSV whose own sign convention wasn't fully
    reconciled against this app's at import time.
    """
    rows = (
        db.query(Transaction)
        .join(Category)
        .options(joinedload(Transaction.category), joinedload(Transaction.account))
        .filter(
            or_(
                and_(Category.kind == CategoryKind.income, Transaction.amount > 0),
                and_(Category.kind == CategoryKind.expense, Transaction.amount < 0),
            )
        )
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
            direction=_is_sign_issue(r),
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
        if _is_sign_issue(txn) is not None:
            txn.amount = -txn.amount
            fixed += 1
        else:
            already_ok += 1
    db.commit()
    return SignIssueFixResult(fixed=fixed, already_ok=already_ok)


@router.get("/duplicates", response_model=list[DuplicateGroup])
def list_duplicate_transactions(db: Session = Depends(get_db)):
    """Transactions already sitting in the database more than once with the
    same date, description, and amount.

    Statement imports already guard against re-importing a duplicate, but
    that can't catch every path in — two overlapping files covering the
    same period, the same statement confirmed into the wrong account and
    then re-confirmed into the right one, or a description that only
    differs by letter case between the two copies. Matching is
    case-insensitive on the description and deliberately ignores which
    account a copy landed in, so this finds whatever slipped through
    either path — the same self-service way sign issues are.
    """
    rows = (
        db.query(Transaction)
        .options(joinedload(Transaction.category), joinedload(Transaction.account))
        .all()
    )
    groups: dict[tuple, list[Transaction]] = defaultdict(list)
    for r in rows:
        key = (r.trans_date, r.description.strip().lower(), float(r.amount))
        groups[key].append(r)

    result = [
        DuplicateGroup(
            trans_date=txns[0].trans_date,
            description=txns[0].description,
            amount=float(txns[0].amount),
            category=txns[0].category.name if txns[0].category else None,
            copies=[
                DuplicateTransactionCopy(
                    id=t.id, account_name=t.account.name if t.account else ""
                )
                for t in sorted(txns, key=lambda t: t.id)
            ],
        )
        for txns in groups.values()
        if len(txns) > 1
    ]
    result.sort(key=lambda g: g.trans_date, reverse=True)
    return result


@router.post("/duplicates/fix", response_model=DuplicateFixResult)
def fix_duplicate_transactions(payload: DuplicateFixRequest, db: Session = Depends(get_db)):
    if not payload.transaction_ids:
        raise HTTPException(400, "No transactions selected")
    deleted = 0
    for transaction_id in payload.transaction_ids:
        txn = db.get(Transaction, transaction_id)
        if txn is None:
            continue
        db.delete(txn)
        deleted += 1
    db.commit()
    return DuplicateFixResult(deleted=deleted)
