"""Per-account CSV sign-convention memory. All merchants and amounts
fabricated.

Reproduces a real report: several transactions on one account were
categorized correctly but stored with the wrong amount sign. Root cause —
the single-Amount-column CSV heuristic (see test_csv_parser.py) re-guesses
a file's sign convention from scratch on every import, purely by counting
positive vs. negative rows in that file; a period with relatively few
debits can get the guess wrong, and re-importing the same statement would
reproduce the exact same wrong signs. This locks in whichever decision an
account's first such CSV made, so every later import for that account
trusts it instead of re-guessing.
"""

import asyncio
from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Account, AccountType
from app.routers.statements import confirm_statement, preview_statement
from app.schemas import ImportRequest, ParsedTransaction

SIMPLII_STYLE_CSV = """Date,Description,Amount
2026-07-02,SAMPLE GROCER,-84.20
2026-07-03,SAMPLE COFFEE,-6.75
2026-07-05,SAMPLE GAS BAR,-52.00
2026-07-14,PAYROLL DEPOSIT SAMPLE CORP,2140.00
2026-07-20,SAMPLE PHARMACY,-31.10
"""

# A deposit-heavy period: the majority-vote heuristic alone would call this
# a tie-or-positive-majority and leave it unflipped, even on an account
# that actually uses the ledger (Simplii-style) convention.
DEPOSIT_HEAVY_CSV = """Date,Description,Amount
2026-08-01,SAMPLE WITHDRAWAL,-40.00
2026-08-02,SAMPLE DEPOSIT,500.00
"""


class _FakeUpload:
    def __init__(self, filename, content, content_type="text/csv"):
        self.filename = filename
        self.content_type = content_type
        self._content = content

    async def read(self):
        return self._content


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _account(db, name="Sample Chequing"):
    account = Account(name=name, account_type=AccountType.chequing)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def _preview(db, csv_text, account_id=None):
    upload = _FakeUpload("statement.csv", csv_text.encode("utf-8"))
    return asyncio.run(
        preview_statement(file=upload, statement_year=2026, account_id=account_id, db=db)
    )


# A minimal handcrafted empty PDF — no real statement content, just enough
# structure for pdfplumber to open it as an (empty) one-page document.
EMPTY_PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]/Resources<<>>>>endobj\n"
    b"trailer<</Root 1 0 R>>\n"
    b"%%EOF"
)


def _preview_pdf(db):
    upload = _FakeUpload("statement.pdf", EMPTY_PDF_BYTES, content_type="application/pdf")
    return asyncio.run(
        preview_statement(file=upload, statement_year=2026, account_id=None, db=db)
    )


def _confirm(db, account_id, amount_sign_flipped, transactions=None):
    return confirm_statement(
        ImportRequest(
            account_id=account_id,
            transactions=transactions or [],
            amount_sign_flipped=amount_sign_flipped,
        ),
        db=db,
    )


def test_first_preview_for_an_account_with_no_history_uses_the_heuristic(db):
    account = _account(db)
    preview = _preview(db, SIMPLII_STYLE_CSV, account_id=account.id)
    assert preview.flip_amount_sign_applied is True
    grocer = next(t for t in preview.transactions if "GROCER" in t.description)
    assert grocer.amount == 84.20


def test_preview_without_an_account_id_still_falls_back_to_the_heuristic(db):
    preview = _preview(db, SIMPLII_STYLE_CSV)
    assert preview.flip_amount_sign_applied is True


def test_confirming_locks_in_the_decision_for_a_fresh_account(db):
    account = _account(db)
    assert account.csv_amount_sign_flipped is None
    _confirm(db, account.id, amount_sign_flipped=True)
    db.refresh(account)
    assert account.csv_amount_sign_flipped is True


def test_confirming_never_overwrites_an_already_locked_in_decision(db):
    account = _account(db)
    _confirm(db, account.id, amount_sign_flipped=False)
    db.refresh(account)
    assert account.csv_amount_sign_flipped is False
    # A later import's own decision (even a different one) must not
    # override the account's established convention.
    _confirm(db, account.id, amount_sign_flipped=True)
    db.refresh(account)
    assert account.csv_amount_sign_flipped is False


def test_confirming_a_pdf_or_two_column_import_leaves_the_flag_untouched(db):
    account = _account(db)
    _confirm(db, account.id, amount_sign_flipped=None)
    db.refresh(account)
    assert account.csv_amount_sign_flipped is None


def test_a_locked_in_decision_overrides_a_disagreeing_heuristic_on_the_next_import(db):
    """The actual bug this prevents: a deposit-heavy period that the raw
    heuristic would misjudge gets the right answer anyway once the
    account's real convention is known."""
    account = _account(db)
    _confirm(db, account.id, amount_sign_flipped=True)  # established from an earlier import

    unforced_check = _preview(db, DEPOSIT_HEAVY_CSV)  # sanity: heuristic alone disagrees
    assert unforced_check.flip_amount_sign_applied is False

    preview = _preview(db, DEPOSIT_HEAVY_CSV, account_id=account.id)
    assert preview.flip_amount_sign_applied is True
    withdrawal = next(t for t in preview.transactions if "WITHDRAWAL" in t.description)
    assert withdrawal.amount == 40.00


def test_a_locked_in_false_decision_also_overrides_the_heuristic(db):
    account = _account(db)
    _confirm(db, account.id, amount_sign_flipped=False)

    preview = _preview(db, SIMPLII_STYLE_CSV, account_id=account.id)
    assert preview.flip_amount_sign_applied is False
    grocer = next(t for t in preview.transactions if "GROCER" in t.description)
    assert grocer.amount == -84.20  # left exactly as the file had it


def test_confirming_still_requires_a_real_account(db):
    with pytest.raises(HTTPException) as exc_info:
        confirm_statement(
            ImportRequest(account_id=999, transactions=[], amount_sign_flipped=True),
            db=db,
        )
    assert exc_info.value.status_code == 404


def test_locking_in_does_not_block_the_normal_import(db):
    account = _account(db)
    txn = ParsedTransaction(
        trans_date=date(2026, 7, 2), description="SAMPLE GROCER", amount=84.20
    )
    result = _confirm(db, account.id, amount_sign_flipped=True, transactions=[txn])
    assert result["imported"] == 1
    db.refresh(account)
    assert account.csv_amount_sign_flipped is True


# --- is_credit_card_statement: lets the frontend warn on a mismatched account ---


def test_a_csv_preview_is_not_flagged_as_a_credit_card_statement(db):
    preview = _preview(db, SIMPLII_STYLE_CSV)
    assert preview.is_credit_card_statement is False


def test_a_pdf_preview_is_flagged_as_a_credit_card_statement(db):
    preview = _preview_pdf(db)
    assert preview.is_credit_card_statement is True
