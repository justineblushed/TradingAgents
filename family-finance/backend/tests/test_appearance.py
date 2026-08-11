"""Category colour and emoji: defaults, validation, and the migration backfill."""

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.categorize import DEFAULT_APPEARANCE, DEFAULT_RULES, seed_default_categories
from app.db import Base
from app.models import Category
from app.routers.categories import set_appearance
from app.schemas import CategoryAppearanceUpdate


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _reloaded_db():
    """Re-bind app.db (and the models registered on its Base) to whatever
    DATABASE_URL currently says. app.db builds its engine at import time, so
    pointing it at a temp file means reloading it — and app.models has to be
    reloaded too, or the fresh Base.metadata has no tables registered and
    create_all() silently does nothing."""
    from importlib import reload

    from app import config, db as db_module, models

    reload(config)
    reload(db_module)
    reload(models)
    return db_module


# --- defaults -----------------------------------------------------------------


def test_every_built_in_category_has_a_colour_and_emoji():
    missing = [name for name in DEFAULT_RULES if name not in DEFAULT_APPEARANCE]
    assert missing == [], f"no appearance defined for {missing}"


def test_default_colours_are_valid_hex():
    for name, (color, _emoji) in DEFAULT_APPEARANCE.items():
        assert color.startswith("#") and len(color) == 7, f"{name}: {color}"
        int(color[1:], 16)  # raises if not hex


def test_default_colours_are_distinct():
    """A colour has to identify a category. Two categories sharing one makes
    every chart ambiguous."""
    colors = [c for c, _ in DEFAULT_APPEARANCE.values()]
    assert len(colors) == len(set(colors))


def test_seeding_applies_the_defaults(db):
    seed_default_categories(db)
    groceries = db.query(Category).filter(Category.name == "Groceries").first()
    assert groceries.color == DEFAULT_APPEARANCE["Groceries"][0]
    assert groceries.emoji == DEFAULT_APPEARANCE["Groceries"][1]


def test_no_seeded_category_is_left_without_a_colour(db):
    seed_default_categories(db)
    assert [c.name for c in db.query(Category).filter(Category.color == "").all()] == []


# --- validation ---------------------------------------------------------------


def test_a_valid_colour_and_emoji_are_saved(db):
    seed_default_categories(db)
    groceries = db.query(Category).filter(Category.name == "Groceries").first()
    out = set_appearance(
        groceries.id, CategoryAppearanceUpdate(color="#AB12CD", emoji="🥦"), db
    )
    assert out.color == "#ab12cd"  # normalized
    assert out.emoji == "🥦"


def test_a_non_hex_colour_is_refused(db):
    seed_default_categories(db)
    cid = db.query(Category).first().id
    for bad in ("red", "#fff", "2f6fed", "#12345g", ""):
        with pytest.raises(HTTPException) as excinfo:
            set_appearance(cid, CategoryAppearanceUpdate(color=bad), db)
        assert excinfo.value.status_code == 400


def test_the_emoji_field_is_length_capped(db):
    seed_default_categories(db)
    cid = db.query(Category).first().id
    with pytest.raises(HTTPException) as excinfo:
        set_appearance(
            cid, CategoryAppearanceUpdate(color="#2f6fed", emoji="way too long"), db
        )
    assert excinfo.value.status_code == 400


def test_clearing_the_emoji_is_allowed(db):
    seed_default_categories(db)
    groceries = db.query(Category).filter(Category.name == "Groceries").first()
    out = set_appearance(groceries.id, CategoryAppearanceUpdate(color="#2f6fed"), db)
    assert out.emoji == ""


def test_an_unknown_category_404s(db):
    with pytest.raises(HTTPException) as excinfo:
        set_appearance(999, CategoryAppearanceUpdate(color="#2f6fed"), db)
    assert excinfo.value.status_code == 404


# --- migration backfill -------------------------------------------------------


def test_the_backfill_colours_old_rows_without_touching_chosen_ones(tmp_path):
    """Upgrade path: a database whose categories predate the colour column."""
    import os

    url = f"sqlite:///{tmp_path}/appearance.db"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(Category(name="Groceries", color="", emoji=""))
    session.add(Category(name="A Category The User Made Up", color="", emoji=""))
    session.add(Category(name="Already Chosen", color="#123456", emoji="🦊"))
    session.commit()
    session.close()
    engine.dispose()

    os.environ["DATABASE_URL"] = url
    try:
        db_module = _reloaded_db()
        db_module._ensure_category_appearance()

        check = sessionmaker(bind=create_engine(url))()
        by_name = {c.name: c for c in check.query(Category).all()}

        # Known category picks up its designed colour.
        assert by_name["Groceries"].color == DEFAULT_APPEARANCE["Groceries"][0]
        # A user-invented one still gets *a* colour, just not a designed one.
        assert by_name["A Category The User Made Up"].color.startswith("#")
        assert by_name["A Category The User Made Up"].emoji == ""
        # An explicit choice is never overwritten.
        assert by_name["Already Chosen"].color == "#123456"
        assert by_name["Already Chosen"].emoji == "🦊"
        check.close()
    finally:
        del os.environ["DATABASE_URL"]
        _reloaded_db()


def test_the_backfill_is_idempotent(tmp_path):
    import os

    url = f"sqlite:///{tmp_path}/twice.db"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(Category(name="Groceries", color="", emoji=""))
    session.commit()
    session.close()
    engine.dispose()

    os.environ["DATABASE_URL"] = url
    try:
        db_module = _reloaded_db()
        db_module._ensure_category_appearance()
        check = sessionmaker(bind=create_engine(url))()
        first = check.query(Category).first().color
        check.close()

        db_module._ensure_category_appearance()
        check = sessionmaker(bind=create_engine(url))()
        assert check.query(Category).first().color == first
        check.close()
    finally:
        del os.environ["DATABASE_URL"]
        _reloaded_db()


def test_the_column_migration_runs_on_a_pre_colour_database(tmp_path):
    """ALTER TABLE path: a real database whose categories table predates the
    colour column. Exercises init_db() end to end, not just the backfill."""
    import os
    import sqlite3

    path = f"{tmp_path}/precolor.db"
    # Build the current schema, then take the two new columns back out — that
    # is exactly the shape an existing install is in before upgrading, and it
    # keeps this test from drifting as other tables change.
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(bind=engine)
    engine.dispose()
    con = sqlite3.connect(path)
    con.execute("ALTER TABLE categories DROP COLUMN color")
    con.execute("ALTER TABLE categories DROP COLUMN emoji")
    con.execute(
        "INSERT INTO categories (name, kind, group_name, cost_type, controllability) "
        "VALUES ('Groceries', 'expense', 'Food', 'variable', 'medium')"
    )
    con.commit()
    con.close()

    os.environ["DATABASE_URL"] = f"sqlite:///{path}"
    try:
        db_module = _reloaded_db()
        db_module.init_db()

        con = sqlite3.connect(path)
        cols = [r[1] for r in con.execute("pragma table_info(categories)")]
        assert "color" in cols and "emoji" in cols
        color = con.execute(
            "select color from categories where name = 'Groceries'"
        ).fetchone()[0]
        assert color == DEFAULT_APPEARANCE["Groceries"][0]
        con.close()
    finally:
        del os.environ["DATABASE_URL"]
        _reloaded_db()
