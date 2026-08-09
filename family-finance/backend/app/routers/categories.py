from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.categorize import seed_default_categories
from app.db import get_db
from app.models import Category
from app.schemas import CategoryOut

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    seed_default_categories(db)
    return db.query(Category).order_by(Category.name).all()
