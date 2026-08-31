"""Undoing a single confirmed import. All merchants, dates, and amounts
fabricated.

Reproduces a real report: a credit card PDF statement got confirmed into
the wrong account by mistake (picked the wrong one in the dropdown, not
paying close attention), landing ~100 transactions somewhere they don't
belong. The existing Duplicates finder and Sign Check don't help — these
rows aren't duplicates or sign-mismatched, they're just on the wrong
account. Reset All would fix it but also erases every other account's
history along with it. This is the precise fix: find and undo exactly the
one statement that went to the wrong place, without touching anything
else.
"""

from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import (
    Account,
    AccountType,
    Category,
    CategoryKind,
    Statement,
    Tag,
    Transaction,
)
from app.routers.statements import delete_statement, list_statements


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


def _seed_statement(db, account_id, period_label, count):
    statement = Statement(account_id=account_id, period_label=period_label, transaction_count=count)
    db.add(statement)
    db.flush()
    for i in range(count):
        db.add(
            Transaction(
                account_id=account_id,
                statement_id=statement.id,
                trans_date=date(2026, 7, i % 28 + 1),
                description=f"SAMPLE TXN {i}",
                amount=10.00 + i,
                category_id=_cat(db, "Groceries").id,
            )
        )
    db.commit()
    return statement


def test_list_statements_returns_every_import_newest_first(db):
    _seed_statement(db, account_id=1, period_label="Jun 2026", count=3)
    _seed_statement(db, account_id=1, period_label="Jul 2026", count=5)
    rows = list_statements(account_id=None, db=db)
    assert [r.period_label for r in rows] == ["Jul 2026", "Jun 2026"]


def test_list_statements_filters_by_account(db):
    _seed_statement(db, account_id=1, period_label="Chequing Statement", count=2)
    _seed_statement(db, account_id=2, period_label="Card Statement", count=3)
    rows = list_statements(account_id=2, db=db)
    assert len(rows) == 1
    assert rows[0].period_label == "Card Statement"
    assert rows[0].account_name == "Sample Credit Card"
    assert rows[0].transaction_count == 3


def test_undoing_deletes_only_that_statements_transactions(db):
    """The reported bug's exact shape: a card statement confirmed into
    the wrong account, then undone without disturbing anything else."""
    wrong = _seed_statement(db, account_id=1, period_label="Card statement (wrong account)", count=97)
    _seed_statement(db, account_id=2, period_label="Correct card statement", count=12)

    result = delete_statement(wrong.id, db=db)
    assert result.deleted_transactions == 97

    assert db.query(Transaction).filter(Transaction.account_id == 1).count() == 0
    assert db.query(Transaction).filter(Transaction.account_id == 2).count() == 12
    assert db.query(Statement).filter(Statement.account_id == 2).count() == 1


def test_undoing_removes_the_statement_record_itself(db):
    statement = _seed_statement(db, account_id=1, period_label="Jul 2026", count=4)
    delete_statement(statement.id, db=db)
    assert db.get(Statement, statement.id) is None
    assert list_statements(account_id=1, db=db) == []


def test_undoing_a_nonexistent_statement_404s(db):
    with pytest.raises(HTTPException) as exc_info:
        delete_statement(999, db=db)
    assert exc_info.value.status_code == 404


def test_undoing_cleans_up_tag_associations(db):
    """ORM-level delete (not a bulk query.delete()) so the many-to-many
    tags association is cleaned up along with each row."""
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

    delete_statement(statement.id, db=db)

    remaining_tag = db.query(Tag).filter(Tag.name == "Sample Trip").first()
    assert remaining_tag is not None
    assert remaining_tag.transactions == []


def test_undoing_one_statement_leaves_other_statements_on_the_same_account_alone(db):
    keep = _seed_statement(db, account_id=1, period_label="Jun 2026", count=2)
    wrong = _seed_statement(db, account_id=1, period_label="Jul 2026 (wrong)", count=6)

    delete_statement(wrong.id, db=db)

    remaining = list_statements(account_id=1, db=db)
    assert len(remaining) == 1
    assert remaining[0].id == keep.id
    assert db.query(Transaction).filter(Transaction.account_id == 1).count() == 2
