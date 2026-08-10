"""Keyword-based auto-categorization.

Default rules are seeded into the DB on first run (see seed_default_categories)
and are fully editable afterwards via the /categories API — nothing here is
hardcoded once the app is running against a real database.

Taxonomy principles (agreed with the household):
- Categories describe the *nature of the spending*, grouped for dashboard
  roll-ups (Housing, Transportation, Food, ...). Trip/project labeling and
  essential-vs-discretionary belong to separate dimensions, not more
  categories.
- "Miscellaneous" and "Other Income" deliberately have NO keywords: they're
  manual fallbacks. Auto-filing everything unknown into Misc would quietly
  grow a black-hole category nobody can read.
- Transfers (paying your own credit card, moving money between accounts) are
  excluded from spending/income. Merchant refunds are NOT transfers — they
  stay in their expense category and offset it.
"""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models import Category, CategoryKind, CategoryRule


@dataclass
class DefaultCategory:
    keywords: list[str] = field(default_factory=list)
    kind: CategoryKind = CategoryKind.expense
    group: str = ""


DEFAULT_RULES: dict[str, DefaultCategory] = {
    # --- Housing ---
    "Mortgage": DefaultCategory(["mortgage"], group="Housing"),
    "Property Tax & Insurance": DefaultCategory(
        ["property tax", "tipp", "home insurance", "red river mutual"], group="Housing"
    ),
    "Utilities": DefaultCategory(
        ["hydro", "water bill", "gas bill", "heating"], group="Housing"
    ),
    "Internet & Phone": DefaultCategory(
        ["rogers", "shaw", "telus", "bell canada", "internet bill"], group="Housing"
    ),
    "Home Maintenance": DefaultCategory(
        ["home depot", "rona", "canadian tire", "mcmunn"], group="Housing"
    ),
    # --- Transportation ---
    "Car Payment": DefaultCategory(
        ["ford credit", "car loan", "car installment"], group="Transportation"
    ),
    "Gas & Parking": DefaultCategory(
        ["shell", "costco gas", "petro", "esso", "parkade", "impark", "parking"],
        group="Transportation",
    ),
    "Car Maintenance": DefaultCategory(
        ["oil change", "auto repair", "tires", "kal tire"], group="Transportation"
    ),
    "Car Insurance": DefaultCategory(
        ["manitoba public insurance", "mpi "], group="Transportation"
    ),
    # --- Food ---
    "Groceries": DefaultCategory(
        ["superstore", "walmart", "costco wholesale", "lucky supermarket",
         "no frills", "real cdn", "sobeys", "t&t supermarket", "safeway",
         "young trading", "convenience"],
        group="Food",
    ),
    "Dining Out": DefaultCategory(
        ["restaurant", "cafe", "coffee", "bubble tea", "banh mi", "sushi",
         "thai express", "bistro", "bake shop", "burger king", "pho ",
         "panda tea", "bbq"],
        group="Food",
    ),
    # --- Family ---
    "Childcare & Kids": DefaultCategory(
        ["daycare", "childcare", "once upon a child"], group="Family"
    ),
    "Health & Wellness": DefaultCategory(
        ["dental", "pharmacy", "clinic", "medical", "shoppers drug mart"],
        group="Family",
    ),
    # --- Lifestyle ---
    "Shopping": DefaultCategory(
        ["winners", "homesense", "ikea", "amazon", "amzn", "temu", "marshalls"],
        group="Lifestyle",
    ),
    "Subscriptions": DefaultCategory(
        ["netflix", "spotify", "membership fee", "apple.com", "disney"],
        group="Lifestyle",
    ),
    "Entertainment": DefaultCategory(
        ["cineplex", "cinema", "playground", "kidzgo", "treehouse"],
        group="Lifestyle",
    ),
    "Personal Care": DefaultCategory(
        ["hair", "salon", "barber", "beauty", "cosmetic"], group="Lifestyle"
    ),
    # Deliberately keyword-less: a manual fallback, never an auto-dump.
    "Miscellaneous": DefaultCategory([], group="Lifestyle"),
    # --- Travel ---
    "Travel": DefaultCategory(
        ["airbnb", "hertz", "uber", "flair", "hotel", "airline", "best western",
         "air canada", "westjet", "expedia", "motel"],
        group="Travel",
    ),
    # --- Financial ---
    "Bank Fees & Interest": DefaultCategory(
        ["cash interest", "interest charged", "annual fee", "late fee",
         "overdraft", "service charge", "monthly fee"],
        group="Financial",
    ),
    # --- Income ---
    "Employment Income": DefaultCategory(
        ["payroll deposit", "funds transfer pay "], kind=CategoryKind.income, group="Income"
    ),
    "Rental Income": DefaultCategory(
        ["interac e-transfer receive"], kind=CategoryKind.income, group="Income"
    ),
    "Government Benefits": DefaultCategory(
        ["ccb", "gst", "tps", "canada fed"], kind=CategoryKind.income, group="Income"
    ),
    "Other Income": DefaultCategory([], kind=CategoryKind.income, group="Income"),
    # --- Transfers (excluded from spending/income) ---
    "Credit Card Payment": DefaultCategory(
        ["payment, thank you", "payment received", "pre-authorized payment"],
        kind=CategoryKind.transfer,
        group="Transfers",
    ),
    "Account Transfer": DefaultCategory(
        ["account transfer", "transfer to savings", "transfer from savings"],
        kind=CategoryKind.transfer,
        group="Transfers",
    ),
}

GROUP_ORDER = [
    "Housing",
    "Transportation",
    "Food",
    "Family",
    "Lifestyle",
    "Travel",
    "Financial",
    "Income",
    "Transfers",
]


def seed_default_categories(db: Session) -> None:
    existing = {c.name: c for c in db.query(Category).all()}
    changed = False
    for name, default in DEFAULT_RULES.items():
        category = existing.get(name)
        if category is None:
            category = Category(name=name, kind=default.kind, group_name=default.group)
            db.add(category)
            db.flush()
            for keyword in default.keywords:
                db.add(CategoryRule(keyword=keyword, category_id=category.id))
            changed = True
        elif not category.group_name and default.group:
            # Backfill group for categories that predate the group column.
            category.group_name = default.group
            changed = True
    if changed:
        db.commit()


def suggest_category(db: Session, description: str) -> str | None:
    lowered = description.lower()
    for rule in db.query(CategoryRule).all():
        if rule.keyword in lowered:
            return rule.category.name
    return None
