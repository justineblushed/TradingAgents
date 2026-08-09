"""Keyword-based auto-categorization.

Default rules are seeded into the DB on first run (see seed_default_categories)
and are fully editable afterwards via the /categories API — nothing here is
hardcoded once the app is running against a real database.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import Category, CategoryRule


@dataclass
class DefaultCategory:
    keywords: list[str]
    is_income: bool = False


# Matches the categories actually used in the household's own transaction
# tracking, so day-one suggestions line up with existing habits instead of a
# generic placeholder taxonomy nobody asked for.
DEFAULT_RULES: dict[str, DefaultCategory] = {
    "Grocery": DefaultCategory(
        ["superstore", "walmart", "costco wholesale", "lucky supermarket",
         "no frills", "real cdn", "sobeys", "convenience"]
    ),
    "Dine out": DefaultCategory(
        ["restaurant", "cafe", "coffee", "bubble tea", "banh mi", "sushi",
         "thai express", "bistro", "bake shop", "burger king", "pho "]
    ),
    "Gas, Parking": DefaultCategory(
        ["shell", "costco gas", "parkade", "impark", "gas station"]
    ),
    "Mortgage": DefaultCategory(["mortgage"]),
    "House tax, insurance": DefaultCategory(["insurance", "tipp", "property tax"]),
    "Hydro, Water": DefaultCategory(["hydro", "water bill"]),
    "Internet & phone": DefaultCategory(["rogers", "shaw", "telus", "bell canada"]),
    "Car installment": DefaultCategory(["ford credit", "car loan", "car installment"]),
    "Car Maintenance": DefaultCategory(["manitoba public insurance", "auto repair"]),
    "Subscriptions": DefaultCategory(
        ["netflix", "membership fee", "monthly fee", "apple.com"]
    ),
    "Travel": DefaultCategory(["airbnb", "hertz", "uber", "flair", "hotel", "airline"]),
    "Kids / Childcare": DefaultCategory(["daycare", "childcare"]),
    "Misc spending": DefaultCategory(["temu", "amzn", "amazon", "home depot", "rona", "ikea"]),
    "Payroll": DefaultCategory(["payroll deposit", "funds transfer pay "], is_income=True),
    "Rental Income": DefaultCategory(["interac e-transfer receive"], is_income=True),
    "CCB / GST": DefaultCategory(["ccb", "gst credit"], is_income=True),
}


def seed_default_categories(db: Session) -> None:
    existing = {c.name for c in db.query(Category).all()}
    for name, default in DEFAULT_RULES.items():
        if name in existing:
            continue
        category = Category(name=name, is_income=default.is_income)
        db.add(category)
        db.flush()
        for keyword in default.keywords:
            db.add(CategoryRule(keyword=keyword, category_id=category.id))
    db.commit()


def suggest_category(db: Session, description: str) -> str | None:
    lowered = description.lower()
    for rule in db.query(CategoryRule).all():
        if rule.keyword in lowered:
            return rule.category.name
    return None
