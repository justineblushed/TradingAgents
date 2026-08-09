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


@router.post("/confirm")
def confirm_statement(payload: ImportRequest, db: Session = Depends(get_db)):
    account = db.get(Account, payload.account_id)
    if account is None:
        raise HTTPException(404, "Account not found")

    statement = Statement(
        account_id=account.id,
        period_label=payload.period_label,
        transaction_count=len(payload.transactions),
    )
    db.add(statement)
    db.flush()

    categories_by_name = {c.name: c for c in db.query(Category).all()}

    for txn in payload.transactions:
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
    return {"statement_id": statement.id, "imported": len(payload.transactions)}
