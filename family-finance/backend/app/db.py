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


def _migrate_existing_tables() -> None:
    """Additive, hand-rolled migrations for columns added after the initial
    schema. There's no Alembic here — this is a personal single-file SQLite
    database, so a few explicit ALTER TABLEs are simpler and safer than
    pulling in a migration framework. Base.metadata.create_all() only
    creates *missing* tables; it never alters existing ones, so this runs
    right after it to bring older databases up to date without losing data.
    """
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
            # An earlier default taxonomy used "Payments & Credits" for card
            # payments, filed as a plain expense — force it to transfer so
            # already-imported payments retroactively stop counting as
            # spending, matching what "Credit Card Payment" means going forward.
            conn.execute(
                text(
                    "UPDATE categories SET kind = 'transfer' WHERE name = 'Payments & Credits'"
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


def init_db() -> None:
    from app import models  # noqa: F401  (ensure models are registered)

    Base.metadata.create_all(bind=engine)
    _migrate_existing_tables()
