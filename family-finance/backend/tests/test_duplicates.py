"""Retroactive duplicate-transaction detection and cleanup. All merchants,
dates, and amounts fabricated.

Reproduces a real report: the same transaction (same account, date,
description, amount) ending up twice in the database — from a re-uploaded
statement imported with "keep duplicates," or two files covering an
overlapping period. Import-time duplicate detection can't catch every path
that leads there, so this is the after-the-fact cleanup tool.
"""

from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Account, AccountType, Category, CategoryKind, Transaction
from app.routers.transactions import fix_duplicate_transactions, list_duplicate_transactions
from app.schemas import DuplicateFixRequest


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(Account(name="Sample Chequing", account_type=AccountType.chequing))
    session.add(Category(name="Shopping", kind=CategoryKind.expense))
    session.commit()
    try:
        yield session
    finally:
        session.close()


def _cat(db, name):
    return db.query(Category).filter(Category.name == name).first()


def _txn(db, day, description, amount, category=None):
    db.add(
        Transaction(
            account_id=1,
            trans_date=day,
            description=description,
            amount=amount,
            category_id=_cat(db, category).id if category else None,
        )
    )
    db.commit()


def test_an_exact_repeat_is_flagged(db):
    """This is the reported bug's exact shape: the same real transaction
    ending up twice."""
    _txn(db, date(2026, 4, 29), "EFT PREAUTHORIZED DEBIT WISE CANADA", 811.38, "Shopping")
    _txn(db, date(2026, 4, 29), "EFT PREAUTHORIZED DEBIT WISE CANADA", 811.38, "Shopping")
    groups = list_duplicate_transactions(db=db)
    assert len(groups) == 1
    assert groups[0].description == "EFT PREAUTHORIZED DEBIT WISE CANADA"
    assert groups[0].amount == 811.38
    assert len(groups[0].transaction_ids) == 2


def test_a_single_transaction_is_not_flagged(db):
    _txn(db, date(2026, 4, 29), "SAMPLE GROCER", 40.00, "Shopping")
    groups = list_duplicate_transactions(db=db)
    assert groups == []


def test_two_legitimately_identical_charges_on_different_days_are_not_flagged(db):
    """Same merchant, same amount, different day — a recurring charge, not a
    duplicate import."""
    _txn(db, date(2026, 4, 1), "SAMPLE SUBSCRIPTION", 15.99, "Shopping")
    _txn(db, date(2026, 5, 1), "SAMPLE SUBSCRIPTION", 15.99, "Shopping")
    groups = list_duplicate_transactions(db=db)
    assert groups == []


def test_a_genuine_same_day_double_purchase_is_still_flagged(db):
    """Two identical $8 parking charges on the same real day look exactly
    like a duplicate import from the data alone — there's no way to tell
    them apart, so this is a deliberate false-positive the user resolves by
    simply not deleting anything for that group."""
    _txn(db, date(2026, 4, 15), "SAMPLE PARKADE", 8.00, "Shopping")
    _txn(db, date(2026, 4, 15), "SAMPLE PARKADE", 8.00, "Shopping")
    groups = list_duplicate_transactions(db=db)
    assert len(groups) == 1


def test_three_copies_are_reported_as_one_group_of_three(db):
    for _ in range(3):
        _txn(db, date(2026, 4, 29), "SAMPLE TRIPLE IMPORT", 100.00, "Shopping")
    groups = list_duplicate_transactions(db=db)
    assert len(groups) == 1
    assert len(groups[0].transaction_ids) == 3


def test_groups_are_newest_first(db):
    _txn(db, date(2026, 1, 1), "SAMPLE OLD", 10.00, "Shopping")
    _txn(db, date(2026, 1, 1), "SAMPLE OLD", 10.00, "Shopping")
    _txn(db, date(2026, 6, 1), "SAMPLE NEW", 20.00, "Shopping")
    _txn(db, date(2026, 6, 1), "SAMPLE NEW", 20.00, "Shopping")
    groups = list_duplicate_transactions(db=db)
    assert [g.description for g in groups] == ["SAMPLE NEW", "SAMPLE OLD"]


def test_fixing_deletes_only_the_selected_copies(db):
    _txn(db, date(2026, 4, 29), "SAMPLE DUP", 50.00, "Shopping")
    _txn(db, date(2026, 4, 29), "SAMPLE DUP", 50.00, "Shopping")
    ids = list_duplicate_transactions(db=db)[0].transaction_ids
    result = fix_duplicate_transactions(DuplicateFixRequest(transaction_ids=[ids[0]]), db=db)
    assert result.deleted == 1
    remaining = db.query(Transaction).filter(Transaction.description == "SAMPLE DUP").all()
    assert len(remaining) == 1
    assert remaining[0].id == ids[1]


def test_fixing_resolves_the_group_entirely_when_deleting_all_but_one(db):
    _txn(db, date(2026, 4, 29), "SAMPLE DUP", 50.00, "Shopping")
    _txn(db, date(2026, 4, 29), "SAMPLE DUP", 50.00, "Shopping")
    ids = list_duplicate_transactions(db=db)[0].transaction_ids
    fix_duplicate_transactions(DuplicateFixRequest(transaction_ids=[ids[0]]), db=db)
    assert list_duplicate_transactions(db=db) == []


def test_fixing_a_nonexistent_id_is_silently_skipped(db):
    _txn(db, date(2026, 4, 29), "SAMPLE DUP", 50.00, "Shopping")
    _txn(db, date(2026, 4, 29), "SAMPLE DUP", 50.00, "Shopping")
    result = fix_duplicate_transactions(DuplicateFixRequest(transaction_ids=[999]), db=db)
    assert result.deleted == 0


def test_fixing_with_no_ids_selected_is_refused(db):
    with pytest.raises(HTTPException) as exc_info:
        fix_duplicate_transactions(DuplicateFixRequest(transaction_ids=[]), db=db)
    assert exc_info.value.status_code == 400


def test_fixing_one_group_leaves_other_groups_untouched(db):
    _txn(db, date(2026, 4, 29), "SAMPLE DUP A", 50.00, "Shopping")
    _txn(db, date(2026, 4, 29), "SAMPLE DUP A", 50.00, "Shopping")
    _txn(db, date(2026, 4, 30), "SAMPLE DUP B", 75.00, "Shopping")
    _txn(db, date(2026, 4, 30), "SAMPLE DUP B", 75.00, "Shopping")

    groups = list_duplicate_transactions(db=db)
    group_a = next(g for g in groups if g.description == "SAMPLE DUP A")
    fix_duplicate_transactions(
        DuplicateFixRequest(transaction_ids=[group_a.transaction_ids[0]]), db=db
    )

    remaining_groups = list_duplicate_transactions(db=db)
    assert len(remaining_groups) == 1
    assert remaining_groups[0].description == "SAMPLE DUP B"
