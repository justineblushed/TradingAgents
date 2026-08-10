from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.health import compute_health

router = APIRouter(prefix="/health-score", tags=["health-score"])


@router.get("")
def health_score(db: Session = Depends(get_db)):
    return compute_health(db)
