"""Retroactive duplicate-transaction detection and cleanup. All merchants,
dates, and amounts fabricated.

Reproduces two real reports: the same transaction (same date, description,
amount) ending up twice in the database — either within one account, from a
re-uploaded statement imported with "keep duplicates" or two files covering
an overlapping period, or across two different accounts, from the same
statement confirmed into the wrong account and then confirmed again into
the right one. Also reproduces a description that only differs by letter
case between the two copies (e.g. a bank inconsistently capitalizing its own
transaction descriptions across statements). Import-time duplicate
detection can't catch either path, so this is the after-the-fact cleanup
tool.
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
    session.add(Account(name="Sample Credit Card", account_type=AccountType.credit_card))
    session.add(Category(name="Shopping", kind=CategoryKind.expense))
    session.commit()
    try:
        yield session
    finally:
        session.close()


def _cat(db, name):
    return db.query(Category).filter(Category.name == name).first()


def _txn(db, day, description, amount, category=None, account_id=1):
    db.add(
        Transaction(
            account_id=account_id,
            trans_date=day,
            description=description,
            amount=amount,
            category_id=_cat(db, category).id if category else None,
        )
    )
    db.commit()


def _copy_ids(group):
    return [c.id for c in group.copies]


def test_an_exact_repeat_is_flagged(db):
    """This is the reported bug's exact shape: the same real transaction
    ending up twice."""
    _txn(db, date(2026, 4, 29), "EFT PREAUTHORIZED DEBIT WISE CANADA", 811.38, "Shopping")
    _txn(db, date(2026, 4, 29), "EFT PREAUTHORIZED DEBIT WISE CANADA", 811.38, "Shopping")
    groups = list_duplicate_transactions(db=db)
    assert len(groups) == 1
    assert groups[0].description == "EFT PREAUTHORIZED DEBIT WISE CANADA"
    assert groups[0].amount == 811.38
    assert len(groups[0].copies) == 2


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
    assert len(groups[0].copies) == 3


def test_groups_are_newest_first(db):
    _txn(db, date(2026, 1, 1), "SAMPLE OLD", 10.00, "Shopping")
    _txn(db, date(2026, 1, 1), "SAMPLE OLD", 10.00, "Shopping")
    _txn(db, date(2026, 6, 1), "SAMPLE NEW", 20.00, "Shopping")
    _txn(db, date(2026, 6, 1), "SAMPLE NEW", 20.00, "Shopping")
    groups = list_duplicate_transactions(db=db)
    assert [g.description for g in groups] == ["SAMPLE NEW", "SAMPLE OLD"]


def test_a_description_that_only_differs_by_case_is_still_flagged(db):
    """A real report: 'Interac E-transfer Receive Sample Person' and
    'INTERAC E-TRANSFER RECEIVE SAMPLE PERSON' on the same day for the same
    amount are the same real transfer, just capitalized inconsistently
    between two statements."""
    _txn(db, date(2026, 8, 3), "Interac E-transfer Receive Sample Person", -550.00)
    _txn(db, date(2026, 8, 3), "INTERAC E-TRANSFER RECEIVE SAMPLE PERSON", -550.00)
    groups = list_duplicate_transactions(db=db)
    assert len(groups) == 1
    assert len(groups[0].copies) == 2


def test_a_duplicate_across_two_accounts_is_flagged(db):
    """A real report: the same preauthorized debit ended up posted to both
    a chequing account and a credit card account — almost certainly the
    same statement confirmed into the wrong account, then confirmed again
    into the right one. Duplicate detection deliberately ignores which
    account a copy landed in, so this is caught even though it wasn't
    before."""
    _txn(db, date(2026, 7, 27), "EFT PREAUTHORIZED DEBIT SAMPLE LOAN CO", 392.50, account_id=1)
    _txn(db, date(2026, 7, 27), "EFT PREAUTHORIZED DEBIT SAMPLE LOAN CO", 392.50, account_id=2)
    groups = list_duplicate_transactions(db=db)
    assert len(groups) == 1
    account_names = {c.account_name for c in groups[0].copies}
    assert account_names == {"Sample Chequing", "Sample Credit Card"}


def test_each_copy_reports_its_own_account_name(db):
    _txn(db, date(2026, 7, 27), "SAMPLE CROSS ACCOUNT DUP", 100.00, account_id=1)
    _txn(db, date(2026, 7, 27), "SAMPLE CROSS ACCOUNT DUP", 100.00, account_id=2)
    group = list_duplicate_transactions(db=db)[0]
    by_account = {c.account_name: c.id for c in group.copies}
    assert set(by_account) == {"Sample Chequing", "Sample Credit Card"}


def test_fixing_deletes_only_the_selected_copies(db):
    _txn(db, date(2026, 4, 29), "SAMPLE DUP", 50.00, "Shopping")
    _txn(db, date(2026, 4, 29), "SAMPLE DUP", 50.00, "Shopping")
    ids = _copy_ids(list_duplicate_transactions(db=db)[0])
    result = fix_duplicate_transactions(DuplicateFixRequest(transaction_ids=[ids[0]]), db=db)
    assert result.deleted == 1
    remaining = db.query(Transaction).filter(Transaction.description == "SAMPLE DUP").all()
    assert len(remaining) == 1
    assert remaining[0].id == ids[1]


def test_fixing_resolves_the_group_entirely_when_deleting_all_but_one(db):
    _txn(db, date(2026, 4, 29), "SAMPLE DUP", 50.00, "Shopping")
    _txn(db, date(2026, 4, 29), "SAMPLE DUP", 50.00, "Shopping")
    ids = _copy_ids(list_duplicate_transactions(db=db)[0])
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
        DuplicateFixRequest(transaction_ids=[_copy_ids(group_a)[0]]), db=db
    )

    remaining_groups = list_duplicate_transactions(db=db)
    assert len(remaining_groups) == 1
    assert remaining_groups[0].description == "SAMPLE DUP B"
