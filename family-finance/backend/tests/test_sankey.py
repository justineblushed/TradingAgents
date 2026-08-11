"""Sankey cash-flow endpoint. All merchants and amounts fabricated.

The property that matters most: whatever this diagram draws must add up to
exactly what /summary reports for the same month. A Sankey that tells a
different story than the KPI cards next to it is worse than no Sankey.
"""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Account, AccountType, Category, CategoryKind, Transaction
from app.routers.dashboard import sankey, summary

MONTH = "2026-07"


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(Account(name="Sample Visa", account_type=AccountType.credit_card))
    session.add(
        Category(
            name="Groceries", kind=CategoryKind.expense, group_name="Food", color="#15803d"
        )
    )
    session.add(
        Category(
            name="Dining Out", kind=CategoryKind.expense, group_name="Food", color="#4ade80"
        )
    )
    session.add(
        Category(
            name="Gas & Parking",
            kind=CategoryKind.expense,
            group_name="Transportation",
            color="#0891b2",
        )
    )
    session.add(
        Category(
            name="Employment Income",
            kind=CategoryKind.income,
            group_name="Income",
            color="#047857",
        )
    )
    session.add(
        Category(
            name="Credit Card Payment", kind=CategoryKind.transfer, group_name="Transfers"
        )
    )
    session.commit()
    try:
        yield session
    finally:
        session.close()


def _cat(db, name):
    return db.query(Category).filter(Category.name == name).first()


def _txn(db, day, description, amount, category):
    db.add(
        Transaction(
            account_id=1,
            trans_date=day,
            description=description,
            amount=amount,
            category_id=_cat(db, category).id if category else None,
        )
    )
    db.commit()


def _node(result, kind, name):
    """Index of the node matching (kind, name) — links reference nodes by
    index, so tests need the index, not the SankeyNode object itself."""
    return next(i for i, n in enumerate(result.nodes) if n.kind == kind and n.name == name)


def _node_obj(result, name):
    return next(n for n in result.nodes if n.name == name)


def _links_from(result, source_index):
    return [l for l in result.links if l.source == source_index]


# --- totals agree with /summary -----------------------------------------------


def test_totals_match_the_dashboard_summary_for_the_same_month(db):
    _txn(db, date(2026, 7, 3), "SAMPLE GROCER", 120.00, "Groceries")
    _txn(db, date(2026, 7, 10), "SAMPLE RESTAURANT", 60.00, "Dining Out")
    _txn(db, date(2026, 7, 14), "PAYROLL DEPOSIT", -3000.00, "Employment Income")

    dash = summary(month=MONTH, db=db)
    diagram = sankey(month=MONTH, db=db)

    assert diagram.total_income == dash.total_income
    assert diagram.total_spending == dash.total_spending
    assert diagram.net_cash_flow == dash.net_cash_flow


def test_transfers_are_excluded_same_as_the_dashboard(db):
    _txn(db, date(2026, 7, 3), "SAMPLE GROCER", 120.00, "Groceries")
    _txn(db, date(2026, 7, 20), "PAYMENT THANK YOU", -500.00, "Credit Card Payment")
    diagram = sankey(month=MONTH, db=db)
    assert diagram.total_spending == 120.00
    assert not any(n.name == "Credit Card Payment" for n in diagram.nodes)


# --- structure: income -> hub -> groups -> categories -------------------------


def test_income_flows_into_the_hub(db):
    _txn(db, date(2026, 7, 14), "PAYROLL DEPOSIT", -3000.00, "Employment Income")
    diagram = sankey(month=MONTH, db=db)
    hub = _node(diagram, "hub", "Income")
    income_node = _node(diagram, "income", "Employment Income")
    link = next(l for l in diagram.links if l.source == income_node and l.target == hub)
    assert link.value == 3000.00


def test_hub_flows_out_to_each_group_sized_by_group_total(db):
    _txn(db, date(2026, 7, 3), "SAMPLE GROCER", 120.00, "Groceries")
    _txn(db, date(2026, 7, 10), "SAMPLE RESTAURANT", 60.00, "Dining Out")
    _txn(db, date(2026, 7, 12), "SHELL GAS", 40.00, "Gas & Parking")

    diagram = sankey(month=MONTH, db=db)
    hub = _node(diagram, "hub", "Income")
    food = _node(diagram, "group", "Food")
    transport = _node(diagram, "group", "Transportation")

    food_link = next(l for l in diagram.links if l.source == hub and l.target == food)
    transport_link = next(l for l in diagram.links if l.source == hub and l.target == transport)
    assert food_link.value == 180.00  # 120 groceries + 60 dining
    assert transport_link.value == 40.00


def test_a_group_with_two_categories_splits_into_leaves(db):
    _txn(db, date(2026, 7, 3), "SAMPLE GROCER", 120.00, "Groceries")
    _txn(db, date(2026, 7, 10), "SAMPLE RESTAURANT", 60.00, "Dining Out")
    diagram = sankey(month=MONTH, db=db)
    food = _node(diagram, "group", "Food")
    leaves = _links_from(diagram, food)
    assert {l.target for l in leaves} == {
        _node(diagram, "category", "Groceries"),
        _node(diagram, "category", "Dining Out"),
    }
    groceries_link = next(
        l for l in leaves if l.target == _node(diagram, "category", "Groceries")
    )
    assert groceries_link.value == 120.00


def test_a_group_with_only_one_category_does_not_duplicate_the_leaf(db):
    """A single-category group has nothing more specific to show — drawing a
    second node with the same name and width as the group would just be
    visual noise, not information."""
    _txn(db, date(2026, 7, 12), "SHELL GAS", 40.00, "Gas & Parking")
    diagram = sankey(month=MONTH, db=db)
    transport = _node(diagram, "group", "Transportation")
    assert _links_from(diagram, transport) == []
    assert not any(n.kind == "category" and n.name == "Gas & Parking" for n in diagram.nodes)


def test_uncategorized_spending_becomes_its_own_group_without_a_duplicate_leaf(db):
    _txn(db, date(2026, 7, 5), "SAMPLE UNKNOWN", 25.00, None)
    diagram = sankey(month=MONTH, db=db)
    uncategorized = _node(diagram, "group", "Uncategorized")
    assert _links_from(diagram, uncategorized) == []


# --- colour ---------------------------------------------------------------


def test_category_nodes_carry_their_own_colour_not_the_groups(db):
    # Two categories so a leaf actually forms (a lone category collapses
    # into its group — see the dedicated test for that). Dining Out is the
    # smaller slice, so if the leaf showed the group's dominant colour
    # instead of its own, this would catch it.
    _txn(db, date(2026, 7, 3), "SAMPLE GROCER", 500.00, "Groceries")
    _txn(db, date(2026, 7, 10), "SAMPLE RESTAURANT", 10.00, "Dining Out")
    diagram = sankey(month=MONTH, db=db)
    dining_node = _node_obj(diagram, "Dining Out")
    assert dining_node.color == "#4ade80"


def test_a_group_is_coloured_after_its_biggest_category(db):
    _txn(db, date(2026, 7, 3), "SAMPLE GROCER", 500.00, "Groceries")
    _txn(db, date(2026, 7, 10), "SAMPLE RESTAURANT", 10.00, "Dining Out")
    diagram = sankey(month=MONTH, db=db)
    food = _node_obj(diagram, "Food")
    assert food.color == "#15803d"  # Groceries' colour, since it's the larger slice


# --- savings vs shortfall -------------------------------------------------


def test_leftover_income_flows_to_a_savings_node(db):
    _txn(db, date(2026, 7, 3), "SAMPLE GROCER", 120.00, "Groceries")
    _txn(db, date(2026, 7, 14), "PAYROLL DEPOSIT", -3000.00, "Employment Income")
    diagram = sankey(month=MONTH, db=db)
    hub = _node(diagram, "hub", "Income")
    savings = _node(diagram, "savings", "Savings")
    link = next(l for l in diagram.links if l.source == hub and l.target == savings)
    assert link.value == pytest.approx(2880.00)
    assert diagram.shortfall is None


def test_overspending_reports_a_shortfall_instead_of_a_fabricated_flow(db):
    """A negative-value link isn't meaningful in a Sankey — when spending
    exceeds income, the gap is a number, not a drawn flow."""
    _txn(db, date(2026, 7, 3), "SAMPLE GROCER", 5000.00, "Groceries")
    _txn(db, date(2026, 7, 14), "PAYROLL DEPOSIT", -3000.00, "Employment Income")
    diagram = sankey(month=MONTH, db=db)
    assert not any(n.kind == "savings" for n in diagram.nodes)
    assert diagram.shortfall == pytest.approx(2000.00)


def test_a_month_with_nothing_returns_an_empty_but_valid_diagram(db):
    diagram = sankey(month="2026-02", db=db)
    assert diagram.nodes == [] or all(n.kind == "hub" for n in diagram.nodes)
    assert diagram.links == []
    assert diagram.total_income == 0
    assert diagram.total_spending == 0
