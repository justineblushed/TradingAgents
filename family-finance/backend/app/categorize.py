"""Keyword-based auto-categorization.

Default rules are seeded into the DB on first run (see seed_default_categories)
and are fully editable afterwards via the /categories API — nothing here is
hardcoded once the app is running against a real database.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import Category, CategoryKind, CategoryRule


@dataclass
class DefaultCategory:
    keywords: list[str]
    kind: CategoryKind = CategoryKind.expense


# Matches the categories actually used in the household's own transaction
# tracking, so day-one suggestions line up with existing habits instead of a
# generic placeholder taxonomy nobody asked for.
#
# "Credit Card Payment" is kind=transfer, not income or expense: paying off
# your own card is money moving between your own accounts, not spending —
# it must never inflate the household spending/income totals.
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
    "Interest & Fees": DefaultCategory(["cash interest", "interest charged", "annual fee", "late fee"]),
    "Credit Card Payment": DefaultCategory(
        ["payment, thank you", "payment received", "pre-authorized payment"],
        kind=CategoryKind.transfer,
    ),
    "Payroll": DefaultCategory(["payroll deposit", "funds transfer pay "], kind=CategoryKind.income),
    "Rental Income": DefaultCategory(["interac e-transfer receive"], kind=CategoryKind.income),
    "CCB / GST": DefaultCategory(["ccb", "gst credit"], kind=CategoryKind.income),
}


def seed_default_categories(db: Session) -> None:
    existing = {c.name for c in db.query(Category).all()}
    for name, default in DEFAULT_RULES.items():
        if name in existing:
            continue
        category = Category(name=name, kind=default.kind)
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
