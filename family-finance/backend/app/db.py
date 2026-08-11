from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import DATABASE_URL

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _column_names(inspector, table_name: str) -> set[str]:
    return {col["name"] for col in inspector.get_columns(table_name)}


def _migrate_existing_tables() -> bool:
    """Additive, hand-rolled migrations for columns added after the initial
    schema. There's no Alembic here — this is a personal single-file SQLite
    database, so a few explicit ALTER TABLEs are simpler and safer than
    pulling in a migration framework. Base.metadata.create_all() only
    creates *missing* tables; it never alters existing ones, so this runs
    right after it to bring older databases up to date without losing data.

    Returns True when the cost_type/controllability columns were just added,
    so the caller can backfill them once the taxonomy renames have run.
    """
    added_classification_columns = False
    inspector = inspect(engine)
    with engine.begin() as conn:
        if inspector.has_table("categories"):
            cols = _column_names(inspector, "categories")
            had_is_income = "is_income" in cols
            if "kind" not in cols:
                conn.execute(text("ALTER TABLE categories ADD COLUMN kind VARCHAR(20) DEFAULT 'expense'"))
                if had_is_income:
                    conn.execute(
                        text("UPDATE categories SET kind = 'income' WHERE is_income = 1")
                    )
            if had_is_income:
                # is_income was NOT NULL with no database-level default. The
                # ORM no longer sets it on insert (kind replaced it), so every
                # new category would violate that constraint until the
                # column itself is gone. (Needs SQLite 3.35+ for DROP COLUMN
                # — universal on any Python 3.9+ install.)
                conn.execute(text("ALTER TABLE categories DROP COLUMN is_income"))
            if "monthly_budget" not in cols:
                conn.execute(
                    text("ALTER TABLE categories ADD COLUMN monthly_budget NUMERIC(12, 2)")
                )
            if "group_name" not in cols:
                conn.execute(
                    text("ALTER TABLE categories ADD COLUMN group_name VARCHAR(40) DEFAULT ''")
                )
            if "color" not in cols:
                conn.execute(
                    text("ALTER TABLE categories ADD COLUMN color VARCHAR(7) DEFAULT ''")
                )
                conn.execute(
                    text("ALTER TABLE categories ADD COLUMN emoji VARCHAR(8) DEFAULT ''")
                )
            if "cost_type" not in cols:
                conn.execute(
                    text("ALTER TABLE categories ADD COLUMN cost_type VARCHAR(20) DEFAULT 'variable'")
                )
                conn.execute(
                    text("ALTER TABLE categories ADD COLUMN controllability VARCHAR(20) DEFAULT 'medium'")
                )
                added_classification_columns = True
            # An earlier default taxonomy used "Payments & Credits" for card
            # payments, filed as a plain expense — force it to transfer so
            # already-imported payments retroactively stop counting as
            # spending, matching what "Credit Card Payment" means going forward.
            conn.execute(
                text(
                    "UPDATE categories SET kind = 'transfer' WHERE name = 'Payments & Credits'"
                )
            )

        if inspector.has_table("category_rules"):
            cols = _column_names(inspector, "category_rules")
            # Rules gained optional narrowing conditions. Existing rows keep
            # NULL bounds and no account, which means "match on keyword
            # alone" — exactly how they behaved before.
            if "min_amount" not in cols:
                conn.execute(
                    text("ALTER TABLE category_rules ADD COLUMN min_amount NUMERIC(12, 2)")
                )
                conn.execute(
                    text("ALTER TABLE category_rules ADD COLUMN max_amount NUMERIC(12, 2)")
                )
                conn.execute(
                    text("ALTER TABLE category_rules ADD COLUMN account_id INTEGER")
                )
                conn.execute(
                    text("ALTER TABLE category_rules ADD COLUMN priority INTEGER DEFAULT 0")
                )

        if inspector.has_table("transactions"):
            cols = _column_names(inspector, "transactions")
            if "category_source" not in cols:
                conn.execute(
                    text("ALTER TABLE transactions ADD COLUMN category_source VARCHAR(10)")
                )
                # Everything already categorized predates the distinction.
                # Marking it "manual" is the conservative read: a retroactive
                # rule run will leave it alone rather than quietly rewriting
                # history the household may have curated by hand.
                conn.execute(
                    text(
                        "UPDATE transactions SET category_source = 'manual' "
                        "WHERE category_id IS NOT NULL"
                    )
                )

        if inspector.has_table("accounts"):
            cols = _column_names(inspector, "accounts")
            if "credit_limit" not in cols:
                conn.execute(text("ALTER TABLE accounts ADD COLUMN credit_limit NUMERIC(12, 2)"))
            # AccountType dropped the old generic "other" member in favour of
            # "other_asset"/"other_liability" — remap any existing rows so the
            # ORM enum can still load them.
            conn.execute(
                text("UPDATE accounts SET account_type = 'other_asset' WHERE account_type = 'other'")
            )

    return added_classification_columns


def _backfill_classification() -> None:
    """Apply the agreed fixed/variable + controllability classification to the
    built-in categories. Runs only right after those columns are created, and
    after the taxonomy renames so names already match the current list — so it
    can never overwrite a classification the user changed later."""
    from app.categorize import DEFAULT_RULES

    with engine.begin() as conn:
        for cat_name, default in DEFAULT_RULES.items():
            conn.execute(
                text(
                    "UPDATE categories SET cost_type = :cost, controllability = :ctrl "
                    "WHERE name = :name"
                ),
                {
                    "cost": default.cost.value,
                    "ctrl": default.control.value,
                    "name": cat_name,
                },
            )


# Old default category names -> their replacement in the current taxonomy.
# Renames happen in place; when the target already exists the two are merged
# (transactions, keywords, and budget move over, the old row is deleted).
CATEGORY_RENAMES: dict[str, str] = {
    "Grocery": "Groceries",
    "Dine out": "Dining Out",
    "Dining": "Dining Out",
    "Gas, Parking": "Gas & Parking",
    "Fuel & Parking": "Gas & Parking",
    "House tax, insurance": "Property Tax & Insurance",
    "Hydro, Water": "Utilities",
    "Internet & phone": "Internet & Phone",
    "Telecom & Utilities": "Internet & Phone",
    "Car installment": "Car Payment",
    "Kids / Childcare": "Childcare & Kids",
    "Health": "Health & Wellness",
    "Misc spending": "Miscellaneous",
    "Interest & Fees": "Bank Fees & Interest",
    "Travel & Lodging": "Travel",
    "Payroll": "Employment Income",
    "CCB / GST": "Government Benefits",
    "Payments & Credits": "Credit Card Payment",
}


def _migrate_category_taxonomy() -> None:
    """Rename/merge categories from earlier default taxonomies into the
    current one, carrying transactions, keywords, and budgets along.
    Idempotent: once no old names remain, this is a no-op. User-created
    categories (names not in the map) are never touched."""
    from app.models import Category, CategoryKind, CategoryRule, Transaction

    from app.categorize import DEFAULT_RULES

    db = SessionLocal()
    try:
        by_name = {c.name: c for c in db.query(Category).all()}
        for old_name, new_name in CATEGORY_RENAMES.items():
            old = by_name.get(old_name)
            if old is None:
                continue
            target = by_name.get(new_name)
            if target is None:
                # Simple rename; adopt the new taxonomy's kind/group.
                default = DEFAULT_RULES.get(new_name)
                old.name = new_name
                if default is not None:
                    old.kind = default.kind
                    old.group_name = default.group
                by_name[new_name] = old
                del by_name[old_name]
            else:
                # Merge into the existing target, then remove the old row.
                db.query(Transaction).filter(
                    Transaction.category_id == old.id
                ).update({"category_id": target.id})
                db.query(CategoryRule).filter(
                    CategoryRule.category_id == old.id
                ).update({"category_id": target.id})
                if target.monthly_budget is None and old.monthly_budget is not None:
                    target.monthly_budget = old.monthly_budget
                db.delete(old)
                del by_name[old_name]
        db.flush()

        # Dedupe keywords that may now collide after merges.
        seen: set[tuple[int, str]] = set()
        for rule in db.query(CategoryRule).order_by(CategoryRule.id).all():
            key = (rule.category_id, rule.keyword)
            if key in seen:
                db.delete(rule)
            else:
                seen.add(key)
        db.commit()
    finally:
        db.close()


def _ensure_category_appearance() -> None:
    """Give every category a colour, keeping the ones already chosen.

    Runs on every startup rather than once behind a migration flag: it only
    ever fills a blank, so it doubles as the assignment step for categories
    the user creates later. Emoji stays blank when there's no sensible
    default — a wrong icon is worse than none.
    """
    from app.categorize import DEFAULT_APPEARANCE, FALLBACK_COLORS
    from app.models import Category

    db = SessionLocal()
    try:
        categories = db.query(Category).order_by(Category.id).all()
        taken = {c.color for c in categories if c.color}
        changed = False
        for index, category in enumerate(categories):
            if category.color:
                continue
            color, emoji = DEFAULT_APPEARANCE.get(category.name, ("", ""))
            if not color:
                # Prefer a fallback nobody is using yet before repeating one.
                unused = [c for c in FALLBACK_COLORS if c not in taken]
                pool = unused or FALLBACK_COLORS
                color = pool[index % len(pool)]
            category.color = color
            taken.add(color)
            if emoji and not category.emoji:
                category.emoji = emoji
            changed = True
        if changed:
            db.commit()
    finally:
        db.close()


def _seed_tax_data() -> None:
    from app.taxseed import seed_tax_data

    db = SessionLocal()
    try:
        seed_tax_data(db)
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401  (ensure models are registered)

    Base.metadata.create_all(bind=engine)
    needs_classification_backfill = _migrate_existing_tables()
    _migrate_category_taxonomy()
    if needs_classification_backfill:
        _backfill_classification()
    _ensure_category_appearance()
    _seed_tax_data()
