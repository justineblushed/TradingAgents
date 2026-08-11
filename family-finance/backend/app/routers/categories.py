import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.categorize import seed_default_categories
from app.db import get_db
from app.models import (
    Category,
    CategoryKind,
    CategoryRule,
    Controllability,
    CostType,
    Transaction,
)
from app.schemas import (
    CategoryAppearanceUpdate,
    CategoryBudgetUpdate,
    CategoryClassificationUpdate,
    CategoryCreate,
    CategoryKeywordsUpdate,
    CategoryOut,
)

router = APIRouter(prefix="/categories", tags=["categories"])

_VALID_KINDS = {k.value for k in CategoryKind}
_VALID_COST_TYPES = {c.value for c in CostType}
_VALID_CONTROLS = {c.value for c in Controllability}


def _enum_value(value) -> str:
    return value.value if hasattr(value, "value") else (value or "")


def _to_out(category: Category) -> CategoryOut:
    return CategoryOut(
        id=category.id,
        name=category.name,
        kind=category.kind.value if hasattr(category.kind, "value") else category.kind,
        keywords=[r.keyword for r in category.rules],
        monthly_budget=(
            float(category.monthly_budget) if category.monthly_budget is not None else None
        ),
        group_name=category.group_name or "",
        cost_type=_enum_value(category.cost_type),
        controllability=_enum_value(category.controllability),
        color=category.color or "",
        emoji=category.emoji or "",
    )


@router.get("", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    seed_default_categories(db)
    categories = db.query(Category).order_by(Category.name).all()
    return [_to_out(c) for c in categories]


@router.post("", response_model=CategoryOut)
def create_category(payload: CategoryCreate, db: Session = Depends(get_db)):
    name = payload.name.strip()
    if not name:
        raise HTTPException(400, "Category name is required")
    if db.query(Category).filter(Category.name == name).first():
        raise HTTPException(409, "A category with this name already exists")
    if payload.kind not in _VALID_KINDS:
        raise HTTPException(400, f"kind must be one of {sorted(_VALID_KINDS)}")
    category = Category(
        name=name, kind=CategoryKind(payload.kind), group_name=payload.group_name.strip()
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return _to_out(category)


@router.put("/{category_id}/keywords", response_model=CategoryOut)
def set_keywords(
    category_id: int, payload: CategoryKeywordsUpdate, db: Session = Depends(get_db)
):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(404, "Category not found")
    db.query(CategoryRule).filter(CategoryRule.category_id == category_id).delete()
    seen = set()
    for raw in payload.keywords:
        keyword = raw.strip().lower()
        if keyword and keyword not in seen:
            seen.add(keyword)
            db.add(CategoryRule(keyword=keyword, category_id=category_id))
    db.commit()
    db.refresh(category)
    return _to_out(category)


@router.put("/{category_id}/budget", response_model=CategoryOut)
def set_budget(
    category_id: int, payload: CategoryBudgetUpdate, db: Session = Depends(get_db)
):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(404, "Category not found")
    if payload.monthly_budget is not None and payload.monthly_budget < 0:
        raise HTTPException(400, "Budget cannot be negative")
    category.monthly_budget = payload.monthly_budget
    db.commit()
    db.refresh(category)
    return _to_out(category)


@router.put("/{category_id}/classification", response_model=CategoryOut)
def set_classification(
    category_id: int,
    payload: CategoryClassificationUpdate,
    db: Session = Depends(get_db),
):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(404, "Category not found")
    if payload.cost_type not in _VALID_COST_TYPES:
        raise HTTPException(400, f"cost_type must be one of {sorted(_VALID_COST_TYPES)}")
    if payload.controllability not in _VALID_CONTROLS:
        raise HTTPException(
            400, f"controllability must be one of {sorted(_VALID_CONTROLS)}"
        )
    category.cost_type = CostType(payload.cost_type)
    category.controllability = Controllability(payload.controllability)
    db.commit()
    db.refresh(category)
    return _to_out(category)


_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


@router.patch("/{category_id}/appearance", response_model=CategoryOut)
def set_appearance(
    category_id: int, payload: CategoryAppearanceUpdate, db: Session = Depends(get_db)
):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(404, "Category not found")
    color = payload.color.strip()
    if not _HEX.match(color):
        raise HTTPException(400, "Colour must be a hex value like #2f6fed")
    # Emoji are multi-byte and often multi-codepoint (skin tones, ZWJ
    # sequences), so cap by characters rather than trying to validate that
    # something "is" an emoji — the column holds 8.
    emoji = payload.emoji.strip()
    if len(emoji) > 8:
        raise HTTPException(400, "Emoji is too long — use one or two characters")
    category.color = color.lower()
    category.emoji = emoji
    db.commit()
    db.refresh(category)
    return _to_out(category)


@router.delete("/{category_id}")
def delete_category(category_id: int, db: Session = Depends(get_db)):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(404, "Category not found")
    # Deleting a category shouldn't delete the transactions that used it —
    # they fall back to Uncategorized instead of disappearing.
    db.query(Transaction).filter(Transaction.category_id == category_id).update(
        {"category_id": None}
    )
    db.query(CategoryRule).filter(CategoryRule.category_id == category_id).delete()
    db.delete(category)
    db.commit()
    return {"ok": True}
