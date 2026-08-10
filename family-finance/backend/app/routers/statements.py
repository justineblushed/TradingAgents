"""Statement upload → human-reviewed preview → confirmed import.

The uploaded PDF is parsed entirely in memory and never written to disk or
committed anywhere; only the extracted, reviewed transaction rows the user
confirms get persisted to the local database.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.categorize import seed_default_categories, suggest_category
from app.db import get_db
from app.models import Account, Category, Statement, Transaction
from app.parsers.creditcard_statement import parse_credit_card_statement
from app.schemas import ImportRequest, ParsedTransaction, StatementPreview

router = APIRouter(prefix="/statements", tags=["statements"])

_MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20MB — plenty for a statement, guards against abuse


@router.post("/preview", response_model=StatementPreview)
async def preview_statement(
    file: UploadFile = File(...),
    statement_year: int = Form(default_factory=lambda: datetime.utcnow().year),
    db: Session = Depends(get_db),
):
    if file.content_type != "application/pdf":
        raise HTTPException(400, "Only PDF statements are supported right now")

    pdf_bytes = await file.read()
    if len(pdf_bytes) > _MAX_UPLOAD_BYTES:
        raise HTTPException(400, "File too large")

    result = parse_credit_card_statement(pdf_bytes, statement_year=statement_year)
    seed_default_categories(db)

    transactions = [
        ParsedTransaction(
            trans_date=t.trans_date,
            post_date=t.post_date,
            description=t.description,
            amount=t.amount,
            foreign_currency_note=t.foreign_currency_note,
            suggested_category=suggest_category(db, t.description),
        )
        for t in result.transactions
    ]
    return StatementPreview(
        account_last_four=result.account_last_four,
        transactions=transactions,
        warnings=result.warnings,
    )


def _duplicate_flags(
    db: Session, account_id: int, transactions: list[ParsedTransaction]
) -> list[bool]:
    """Flag which incoming transactions already exist for this account.

    A duplicate is a same (date, description, amount) row — but statements
    legitimately contain identical rows (two $8 parking charges on the same
    day), so this counts copies: if the DB has one copy and the upload has
    two, only one is flagged. The first N occurrences of each key are the
    duplicates, where N is how many copies the DB already holds.
    """
    existing: dict[tuple, int] = {}
    rows = db.query(
        Transaction.trans_date, Transaction.description, Transaction.amount
    ).filter(Transaction.account_id == account_id)
    for trans_date, description, amount in rows:
        key = (trans_date, description, float(amount))
        existing[key] = existing.get(key, 0) + 1

    flags = []
    for txn in transactions:
        key = (txn.trans_date, txn.description, float(txn.amount))
        if existing.get(key, 0) > 0:
            existing[key] -= 1
            flags.append(True)
        else:
            flags.append(False)
    return flags


@router.post("/confirm")
def confirm_statement(payload: ImportRequest, db: Session = Depends(get_db)):
    account = db.get(Account, payload.account_id)
    if account is None:
        raise HTTPException(404, "Account not found")
    if payload.on_duplicate not in ("block", "skip", "import"):
        raise HTTPException(400, "on_duplicate must be block, skip, or import")

    dup_flags = _duplicate_flags(db, account.id, payload.transactions)
    duplicate_count = sum(dup_flags)

    if duplicate_count > 0 and payload.on_duplicate == "block":
        raise HTTPException(
            409,
            detail={
                "duplicates": duplicate_count,
                "total": len(payload.transactions),
                "message": "Some of these transactions were already imported for this account — likely a re-uploaded statement.",
            },
        )

    if payload.on_duplicate == "skip":
        to_import = [t for t, dup in zip(payload.transactions, dup_flags) if not dup]
        skipped = duplicate_count
    else:
        to_import = list(payload.transactions)
        skipped = 0

    if not to_import:
        return {"statement_id": None, "imported": 0, "skipped_duplicates": skipped}

    statement = Statement(
        account_id=account.id,
        period_label=payload.period_label,
        transaction_count=len(to_import),
    )
    db.add(statement)
    db.flush()

    categories_by_name = {c.name: c for c in db.query(Category).all()}

    for txn in to_import:
        category_id = None
        if txn.suggested_category and txn.suggested_category in categories_by_name:
            category_id = categories_by_name[txn.suggested_category].id
        db.add(
            Transaction(
                account_id=account.id,
                statement_id=statement.id,
                category_id=category_id,
                trans_date=txn.trans_date,
                post_date=txn.post_date,
                description=txn.description,
                amount=txn.amount,
                foreign_currency_note=txn.foreign_currency_note,
            )
        )

    db.commit()
    return {
        "statement_id": statement.id,
        "imported": len(to_import),
        "skipped_duplicates": skipped,
    }
