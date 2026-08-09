"""Keyword-based auto-categorization.

Default rules are seeded into the DB on first run (see seed_default_categories)
and are fully editable afterwards via the /categories API — nothing here is
hardcoded once the app is running against a real database.
"""

from sqlalchemy.orm import Session

from app.models import Category, CategoryRule

DEFAULT_RULES: dict[str, list[str]] = {
    "Groceries": ["superstore", "dollarama", "co-op", "walmart", "costco", "safeway"],
    "Dining": ["restaurant", "bubble tea", "chicken", "burger", "banh mi", "cafe"],
    "Travel & Lodging": ["hotel", "western", "airbnb", "airlines", "motel"],
    "Fuel & Parking": ["shell", "petro", "esso", "kwik trip", "marathon", "parking"],
    "Telecom & Utilities": ["rogers", "shaw", "bell", "telus", "hydro", "utility"],
    "Health": ["dental", "pharmacy", "clinic", "medical"],
    "Payments & Credits": ["payment, thank you", "refund", "credit adjustment"],
    "Interest & Fees": ["interest", "annual fee", "late fee"],
}


def seed_default_categories(db: Session) -> None:
    existing = {c.name for c in db.query(Category).all()}
    for name, keywords in DEFAULT_RULES.items():
        if name in existing:
            continue
        category = Category(name=name, is_income=False)
        db.add(category)
        db.flush()
        for keyword in keywords:
            db.add(CategoryRule(keyword=keyword, category_id=category.id))
    db.commit()


def suggest_category(db: Session, description: str) -> str | None:
    lowered = description.lower()
    for rule in db.query(CategoryRule).all():
        if rule.keyword in lowered:
            return rule.category.name
    return None
