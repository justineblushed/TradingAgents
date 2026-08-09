from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.categorize import seed_default_categories
from app.db import get_db
from app.models import Category, CategoryRule, Transaction
from app.schemas import CategoryCreate, CategoryKeywordsUpdate, CategoryOut

router = APIRouter(prefix="/categories", tags=["categories"])


def _to_out(category: Category) -> CategoryOut:
    return CategoryOut(
        id=category.id,
        name=category.name,
        is_income=category.is_income,
        keywords=[r.keyword for r in category.rules],
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
    category = Category(name=name, is_income=payload.is_income)
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
