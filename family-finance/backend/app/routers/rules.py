"""Auto-categorization rules and retroactive application.

Rules are the household's own; nothing here is hardcoded. The endpoint that
re-runs them over existing transactions always supports a dry run, and
defaults to the narrowest scope, because a bulk re-categorization that can't
be previewed is a bulk mistake waiting to happen.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.categorize import match_rule, rule_matches
from app.db import get_db
from app.models import (
    Account,
    Category,
    CategoryRule,
    CategorySource,
    Tag,
    Transaction,
)
from app.schemas import (
    RuleApplyChange,
    RuleApplyRequest,
    RuleApplyResult,
    RuleInput,
    RuleOut,
)

router = APIRouter(prefix="/rules", tags=["rules"])

_SCOPES = ("uncategorized", "rule", "all")


def _to_out(rule: CategoryRule, match_count: int = 0) -> RuleOut:
    return RuleOut(
        id=rule.id,
        keyword=rule.keyword,
        category=rule.category.name,
        category_id=rule.category_id,
        min_amount=float(rule.min_amount) if rule.min_amount is not None else None,
        max_amount=float(rule.max_amount) if rule.max_amount is not None else None,
        account_id=rule.account_id,
        account_name=rule.account.name if rule.account else "",
        priority=rule.priority or 0,
        tags=sorted(t.name for t in rule.tags),
        match_count=match_count,
    )


def _resolve_tags(db: Session, names: list[str]) -> list[Tag]:
    resolved: list[Tag] = []
    seen: set[str] = set()
    for raw in names:
        name = raw.strip()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        tag = db.query(Tag).filter(Tag.name == name).first()
        if tag is None:
            tag = Tag(name=name)
            db.add(tag)
            db.flush()
        resolved.append(tag)
    return resolved


def _validate(db: Session, payload: RuleInput) -> Category:
    keyword = payload.keyword.strip()
    if not keyword:
        raise HTTPException(400, "A keyword is required")
    category = db.query(Category).filter(Category.name == payload.category).first()
    if category is None:
        raise HTTPException(404, f"No category named {payload.category!r}")
    if (
        payload.min_amount is not None
        and payload.max_amount is not None
        and payload.min_amount > payload.max_amount
    ):
        raise HTTPException(400, "Minimum amount is above the maximum")
    if payload.account_id is not None and db.get(Account, payload.account_id) is None:
        raise HTTPException(404, "Account not found")
    return category


def _all_transactions(db: Session) -> list[Transaction]:
    return (
        db.query(Transaction)
        .options(
            joinedload(Transaction.category),
            joinedload(Transaction.account),
            joinedload(Transaction.tags),
        )
        .all()
    )


@router.get("", response_model=list[RuleOut])
def list_rules(db: Session = Depends(get_db)):
    rules = (
        db.query(CategoryRule)
        .options(
            joinedload(CategoryRule.category),
            joinedload(CategoryRule.account),
            joinedload(CategoryRule.tags),
        )
        .all()
    )
    transactions = _all_transactions(db)
    counts: dict[int, int] = {}
    for rule in rules:
        counts[rule.id] = sum(
            1
            for t in transactions
            if rule_matches(rule, t.description, float(t.amount), t.account_id)
        )
    rules.sort(key=lambda r: (r.category.name, r.keyword))
    return [_to_out(r, counts.get(r.id, 0)) for r in rules]


@router.post("", response_model=RuleOut)
def create_rule(payload: RuleInput, db: Session = Depends(get_db)):
    category = _validate(db, payload)
    rule = CategoryRule(
        keyword=payload.keyword.strip().lower(),
        category_id=category.id,
        min_amount=payload.min_amount,
        max_amount=payload.max_amount,
        account_id=payload.account_id,
        priority=payload.priority,
    )
    rule.tags = _resolve_tags(db, payload.tags)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return _to_out(rule)


@router.put("/{rule_id}", response_model=RuleOut)
def update_rule(rule_id: int, payload: RuleInput, db: Session = Depends(get_db)):
    rule = db.get(CategoryRule, rule_id)
    if rule is None:
        raise HTTPException(404, "Rule not found")
    category = _validate(db, payload)
    rule.keyword = payload.keyword.strip().lower()
    rule.category_id = category.id
    rule.min_amount = payload.min_amount
    rule.max_amount = payload.max_amount
    rule.account_id = payload.account_id
    rule.priority = payload.priority
    rule.tags = _resolve_tags(db, payload.tags)
    db.commit()
    db.refresh(rule)
    return _to_out(rule)


@router.delete("/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.get(CategoryRule, rule_id)
    if rule is None:
        raise HTTPException(404, "Rule not found")
    rule.tags = []
    db.delete(rule)
    db.commit()
    return {"ok": True}


@router.post("/apply", response_model=RuleApplyResult)
def apply_rules(payload: RuleApplyRequest, db: Session = Depends(get_db)):
    """Re-run every rule over already-imported transactions.

    Defaults to a dry run over uncategorized rows only. Widening the scope
    is an explicit choice, and overwriting hand-set categories is the
    widest one — so the counts always report how many manual rows were
    protected, even when the scope allowed them through.
    """
    if payload.scope not in _SCOPES:
        raise HTTPException(400, f"scope must be one of {', '.join(_SCOPES)}")

    rules = (
        db.query(CategoryRule)
        .options(joinedload(CategoryRule.category), joinedload(CategoryRule.tags))
        .all()
    )
    if not rules:
        raise HTTPException(400, "There are no rules to apply yet")

    considered = changed = unchanged = unmatched = protected = 0
    changes: list[RuleApplyChange] = []

    for txn in _all_transactions(db):
        source = txn.category_source
        if txn.category_id is None:
            in_scope = True
        elif source == CategorySource.manual:
            if payload.scope == "all":
                in_scope = True
            else:
                protected += 1
                continue
        else:
            # Rule-assigned, or legacy with no recorded source.
            in_scope = payload.scope in ("rule", "all")
            if not in_scope:
                continue

        considered += 1
        matched = match_rule(
            rules, txn.description, float(txn.amount), txn.account_id
        )
        if matched is None:
            unmatched += 1
            continue
        if matched.category_id == txn.category_id:
            unchanged += 1
            continue

        existing_tags = {t.name for t in txn.tags}
        tags_added = sorted(t.name for t in matched.tags if t.name not in existing_tags)

        changes.append(
            RuleApplyChange(
                transaction_id=txn.id,
                trans_date=txn.trans_date,
                description=txn.description,
                amount=float(txn.amount),
                account_name=txn.account.name if txn.account else "",
                from_category=txn.category.name if txn.category else None,
                from_source=source.value if source else None,
                to_category=matched.category.name,
                matched_keyword=matched.keyword,
                tags_added=tags_added,
            )
        )
        changed += 1

        if not payload.dry_run:
            txn.category_id = matched.category_id
            txn.category_source = CategorySource.rule
            if matched.tags:
                txn.tags = list({*txn.tags, *matched.tags})

    if not payload.dry_run:
        db.commit()

    return RuleApplyResult(
        dry_run=payload.dry_run,
        scope=payload.scope,
        considered=considered,
        changed=changed,
        unchanged=unchanged,
        unmatched=unmatched,
        protected_manual=protected,
        changes=changes,
    )
