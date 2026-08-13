"""Wiping every imported transaction to start over from scratch. All
merchants, dates, and amounts fabricated.

Exists for the case a sign-convention bug (or any other import mistake)
left enough transactions wrong, across enough accounts, that a targeted
per-row review isn't practical — clear everything statement imports
produced and re-upload from a clean slate. Deliberately scoped to what
imports actually create (transactions, statement-log records, coverage
skips, and each account's learned sign convention) and nothing else —
accounts, categories, rules, tags, pay stubs, and manually-recorded net
worth balances all survive a reset.
"""

from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import (
    Account,
    AccountBalance,
    AccountType,
    Category,
    CategoryKind,
    CoverageSkip,
    Statement,
    Tag,
    Transaction,
)
from app.routers.statements import reset_all_transactions
from app.schemas import ResetAllRequest


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(Account(name="Sample Chequing", account_type=AccountType.chequing))
    session.add(Account(name="Sample Credit Card", account_type=AccountType.credit_card))
    session.add(Category(name="Groceries", kind=CategoryKind.expense))
    session.commit()
    try:
        yield session
    finally:
        session.close()


def _cat(db, name):
    return db.query(Category).filter(Category.name == name).first()


def _seed_transaction(db, account_id=1):
    statement = Statement(account_id=account_id, period_label="Jul 2026", transaction_count=1)
    db.add(statement)
    db.flush()
    db.add(
        Transaction(
            account_id=account_id,
            statement_id=statement.id,
            trans_date=date(2026, 7, 3),
            description="SAMPLE GROCER",
            amount=40.00,
            category_id=_cat(db, "Groceries").id,
        )
    )
    db.add(CoverageSkip(account_id=account_id, month="2026-06"))
    db.commit()


def test_confirm_must_be_true(db):
    with pytest.raises(HTTPException) as exc_info:
        reset_all_transactions(ResetAllRequest(confirm=False), db=db)
    assert exc_info.value.status_code == 400


def test_reset_deletes_all_transactions_across_every_account(db):
    _seed_transaction(db, account_id=1)
    _seed_transaction(db, account_id=2)
    result = reset_all_transactions(ResetAllRequest(confirm=True), db=db)
    assert result.deleted_transactions == 2
    assert db.query(Transaction).count() == 0


def test_reset_deletes_statement_log_records(db):
    _seed_transaction(db, account_id=1)
    result = reset_all_transactions(ResetAllRequest(confirm=True), db=db)
    assert result.deleted_statements == 1
    assert db.query(Statement).count() == 0


def test_reset_deletes_coverage_skips(db):
    _seed_transaction(db, account_id=1)
    result = reset_all_transactions(ResetAllRequest(confirm=True), db=db)
    assert result.deleted_coverage_skips == 1
    assert db.query(CoverageSkip).count() == 0


def test_reset_clears_every_accounts_established_sign_convention(db):
    account1 = db.get(Account, 1)
    account2 = db.get(Account, 2)
    account1.csv_amount_sign_flipped = True
    account2.csv_amount_sign_flipped = False
    db.commit()

    result = reset_all_transactions(ResetAllRequest(confirm=True), db=db)
    assert result.accounts_reset == 2
    db.refresh(account1)
    db.refresh(account2)
    assert account1.csv_amount_sign_flipped is None
    assert account2.csv_amount_sign_flipped is None


def test_reset_leaves_accounts_categories_and_balances_untouched(db):
    account = db.get(Account, 1)
    db.add(AccountBalance(account_id=account.id, as_of_date=date(2026, 7, 31), balance=1000.00))
    db.commit()
    _seed_transaction(db, account_id=1)

    reset_all_transactions(ResetAllRequest(confirm=True), db=db)

    assert db.query(Account).count() == 2
    assert db.query(Category).filter(Category.name == "Groceries").first() is not None
    assert db.query(AccountBalance).count() == 1


def test_reset_with_nothing_to_delete_is_a_safe_no_op(db):
    result = reset_all_transactions(ResetAllRequest(confirm=True), db=db)
    assert result.deleted_transactions == 0
    assert result.deleted_statements == 0
    assert result.deleted_coverage_skips == 0
    assert result.accounts_reset == 0


def test_tags_no_longer_reference_a_deleted_transaction(db):
    """ORM-level delete (not a bulk query.delete()) so the many-to-many
    tags association is cleaned up along with each row, not left as an
    orphaned reference."""
    statement = Statement(account_id=1, period_label="Jul 2026", transaction_count=1)
    db.add(statement)
    db.flush()
    tag = Tag(name="Sample Trip")
    txn = Transaction(
        account_id=1,
        statement_id=statement.id,
        trans_date=date(2026, 7, 3),
        description="SAMPLE HOTEL",
        amount=200.00,
    )
    txn.tags = [tag]
    db.add(txn)
    db.commit()

    reset_all_transactions(ResetAllRequest(confirm=True), db=db)

    remaining_tag = db.query(Tag).filter(Tag.name == "Sample Trip").first()
    assert remaining_tag is not None  # the tag itself survives, unused
    assert remaining_tag.transactions == []
