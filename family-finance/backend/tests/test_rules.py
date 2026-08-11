"""Auto-categorization rule matching and retroactive application.

All merchants and amounts fabricated. The behaviour that matters most here
is what the retroactive run refuses to touch: a bulk re-file that silently
undoes hand corrections would destroy work the household can't get back.
"""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.categorize import match_rule, rule_matches
from app.db import Base
from app.models import (
    Account,
    AccountType,
    Category,
    CategoryKind,
    CategoryRule,
    CategorySource,
    Tag,
    Transaction,
)
from app.routers.rules import apply_rules
from app.schemas import RuleApplyRequest


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    for name in ("Groceries", "Memberships", "Dining Out", "Miscellaneous"):
        session.add(Category(name=name, kind=CategoryKind.expense))
    session.add(Account(name="Sample Visa", account_type=AccountType.credit_card))
    session.add(Account(name="Sample Chequing", account_type=AccountType.chequing))
    session.commit()
    try:
        yield session
    finally:
        session.close()


def _cat(db, name):
    return db.query(Category).filter(Category.name == name).first()


def _acct(db, name):
    return db.query(Account).filter(Account.name == name).first()


def _rule(db, keyword, category, **kw):
    rule = CategoryRule(keyword=keyword, category_id=_cat(db, category).id, **kw)
    db.add(rule)
    db.commit()
    return rule


def _txn(db, description, amount, account="Sample Visa", category=None, source=None):
    txn = Transaction(
        account_id=_acct(db, account).id,
        trans_date=date(2026, 7, 4),
        description=description,
        amount=amount,
        category_id=_cat(db, category).id if category else None,
        category_source=source,
    )
    db.add(txn)
    db.commit()
    return txn


# --- condition matching -------------------------------------------------------


def test_keyword_matches_anywhere_and_ignores_case(db):
    rule = _rule(db, "costco", "Groceries")
    assert rule_matches(rule, "PURCHASE COSTCO WHOLESALE #91", 240.0, 1)
    assert rule_matches(rule, "costco gas", 60.0, 1)
    assert not rule_matches(rule, "SAMPLE GROCER", 240.0, 1)


def test_amount_bounds_narrow_a_rule(db):
    rule = _rule(db, "costco", "Memberships", min_amount=0, max_amount=80)
    assert rule_matches(rule, "COSTCO WHOLESALE", 65.00, 1)
    assert not rule_matches(rule, "COSTCO WHOLESALE", 240.00, 1)


def test_amount_bounds_compare_magnitude_so_refunds_match(db):
    rule = _rule(db, "costco", "Memberships", min_amount=0, max_amount=80)
    # A refund of the membership fee is -65.00 in this app's convention.
    assert rule_matches(rule, "COSTCO REFUND", -65.00, 1)


def test_a_bounded_rule_needs_an_amount_to_judge(db):
    rule = _rule(db, "costco", "Memberships", max_amount=80)
    assert not rule_matches(rule, "COSTCO WHOLESALE", None, 1)


def test_account_condition_narrows_a_rule(db):
    visa = _acct(db, "Sample Visa")
    rule = _rule(db, "e-transfer", "Groceries", account_id=visa.id)
    assert rule_matches(rule, "E-TRANSFER SENT", 50.0, visa.id)
    assert not rule_matches(rule, "E-TRANSFER SENT", 50.0, _acct(db, "Sample Chequing").id)


# --- which rule wins ----------------------------------------------------------


def test_the_more_specific_rule_beats_the_general_one(db):
    _rule(db, "costco", "Groceries")
    _rule(db, "costco", "Memberships", min_amount=0, max_amount=80)
    rules = db.query(CategoryRule).all()

    assert match_rule(rules, "COSTCO WHOLESALE", 65.0, 1).category.name == "Memberships"
    assert match_rule(rules, "COSTCO WHOLESALE", 240.0, 1).category.name == "Groceries"


def test_a_longer_keyword_wins_when_conditions_tie(db):
    _rule(db, "costco", "Groceries")
    _rule(db, "costco gas", "Dining Out")  # stand-in category; the point is the keyword
    rules = db.query(CategoryRule).all()
    assert match_rule(rules, "COSTCO GAS BAR", 60.0, 1).keyword == "costco gas"


def test_priority_overrides_everything_else(db):
    _rule(db, "costco", "Groceries", priority=10)
    _rule(db, "costco", "Memberships", min_amount=0, max_amount=80)
    rules = db.query(CategoryRule).all()
    assert match_rule(rules, "COSTCO WHOLESALE", 65.0, 1).category.name == "Groceries"


def test_no_match_returns_none(db):
    _rule(db, "costco", "Groceries")
    assert match_rule(db.query(CategoryRule).all(), "SAMPLE BOOKSHOP", 20.0, 1) is None


# --- retroactive application --------------------------------------------------


def test_dry_run_reports_changes_without_writing(db):
    _rule(db, "sample grocer", "Groceries")
    txn = _txn(db, "SAMPLE GROCER #12", 84.20)

    result = apply_rules(RuleApplyRequest(scope="uncategorized", dry_run=True), db)
    assert result.changed == 1
    assert result.changes[0].to_category == "Groceries"
    db.refresh(txn)
    assert txn.category_id is None  # nothing written


def test_committing_files_the_transaction(db):
    _rule(db, "sample grocer", "Groceries")
    txn = _txn(db, "SAMPLE GROCER #12", 84.20)

    apply_rules(RuleApplyRequest(scope="uncategorized", dry_run=False), db)
    db.refresh(txn)
    assert txn.category.name == "Groceries"
    assert txn.category_source == CategorySource.rule


def test_a_hand_set_category_survives_the_default_scope(db):
    _rule(db, "sample grocer", "Groceries")
    txn = _txn(db, "SAMPLE GROCER #12", 84.20, category="Dining Out",
               source=CategorySource.manual)

    result = apply_rules(RuleApplyRequest(scope="uncategorized", dry_run=False), db)
    db.refresh(txn)
    assert txn.category.name == "Dining Out"
    assert result.protected_manual == 1
    assert result.changed == 0


def test_a_hand_set_category_also_survives_the_rule_scope(db):
    _rule(db, "sample grocer", "Groceries")
    txn = _txn(db, "SAMPLE GROCER #12", 84.20, category="Dining Out",
               source=CategorySource.manual)

    apply_rules(RuleApplyRequest(scope="rule", dry_run=False), db)
    db.refresh(txn)
    assert txn.category.name == "Dining Out"


def test_the_all_scope_does_overwrite_a_hand_set_category(db):
    _rule(db, "sample grocer", "Groceries")
    txn = _txn(db, "SAMPLE GROCER #12", 84.20, category="Dining Out",
               source=CategorySource.manual)

    result = apply_rules(RuleApplyRequest(scope="all", dry_run=False), db)
    db.refresh(txn)
    assert txn.category.name == "Groceries"
    assert result.changed == 1
    # It was in scope, so it isn't counted as protected.
    assert result.protected_manual == 0


def test_a_rule_assigned_category_is_revised_only_in_the_wider_scope(db):
    _rule(db, "sample grocer", "Groceries")
    txn = _txn(db, "SAMPLE GROCER #12", 84.20, category="Dining Out",
               source=CategorySource.rule)

    apply_rules(RuleApplyRequest(scope="uncategorized", dry_run=False), db)
    db.refresh(txn)
    assert txn.category.name == "Dining Out"  # untouched by the narrow scope

    apply_rules(RuleApplyRequest(scope="rule", dry_run=False), db)
    db.refresh(txn)
    assert txn.category.name == "Groceries"


def test_already_correct_rows_count_as_unchanged_not_changed(db):
    _rule(db, "sample grocer", "Groceries")
    _txn(db, "SAMPLE GROCER #12", 84.20, category="Groceries", source=CategorySource.rule)

    result = apply_rules(RuleApplyRequest(scope="rule", dry_run=True), db)
    assert result.changed == 0
    assert result.unchanged == 1


def test_rows_no_rule_matches_are_reported_separately(db):
    _rule(db, "sample grocer", "Groceries")
    _txn(db, "SAMPLE BOOKSHOP", 22.00)

    result = apply_rules(RuleApplyRequest(scope="uncategorized", dry_run=True), db)
    assert result.unmatched == 1
    assert result.changed == 0


def test_a_rule_can_apply_tags_too(db):
    tag = Tag(name="pets")
    db.add(tag)
    db.commit()
    rule = _rule(db, "sample vet", "Miscellaneous")
    rule.tags = [tag]
    db.commit()
    txn = _txn(db, "SAMPLE VET CLINIC", 180.00)

    result = apply_rules(RuleApplyRequest(scope="uncategorized", dry_run=True), db)
    assert result.changes[0].tags_added == ["pets"]

    apply_rules(RuleApplyRequest(scope="uncategorized", dry_run=False), db)
    db.refresh(txn)
    assert [t.name for t in txn.tags] == ["pets"]


def test_applying_with_no_rules_is_refused_rather_than_silently_doing_nothing(db):
    from fastapi import HTTPException

    _txn(db, "SAMPLE GROCER", 10.0)
    with pytest.raises(HTTPException) as excinfo:
        apply_rules(RuleApplyRequest(scope="uncategorized", dry_run=True), db)
    assert excinfo.value.status_code == 400


def test_an_unknown_scope_is_rejected(db):
    from fastapi import HTTPException

    _rule(db, "sample grocer", "Groceries")
    with pytest.raises(HTTPException) as excinfo:
        apply_rules(RuleApplyRequest(scope="everything", dry_run=True), db)
    assert excinfo.value.status_code == 400
