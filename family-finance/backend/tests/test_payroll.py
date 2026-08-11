"""Payroll, tax and RRSP tests.

All pay stub text and rate tables here are fabricated. The bracket numbers
are deliberately round (10% / 20% / 30%) rather than real CRA figures, so
the tests check the *math*, not a rate table that changes every year.
"""

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import TaxBracket, TaxYearSetting
from app.parsers.paystub import parse_lines
from app.routers.payroll import payroll_summary
from app.taxcalc import estimate_tax, marginal_bracket, rrsp_room, tax_on_income

YEAR = 2099


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    for lower, upper, rate in [(0, 50_000, 0.10), (50_000, 100_000, 0.20), (100_000, None, 0.30)]:
        session.add(
            TaxBracket(
                tax_year=YEAR,
                jurisdiction="federal",
                lower_bound=lower,
                upper_bound=upper,
                rate=rate,
            )
        )
    for lower, upper, rate in [(0, 50_000, 0.05), (50_000, None, 0.10)]:
        session.add(
            TaxBracket(
                tax_year=YEAR,
                jurisdiction="XX",
                lower_bound=lower,
                upper_bound=upper,
                rate=rate,
            )
        )
    session.add(
        TaxYearSetting(
            tax_year=YEAR,
            rrsp_rate=0.18,
            rrsp_dollar_limit=30_000.0,
            federal_basic_personal_amount=10_000.0,
            provincial_basic_personal_amount=10_000.0,
            province="XX",
        )
    )
    session.commit()
    try:
        yield session
    finally:
        session.close()


# --- progressive bracket math -------------------------------------------------


def _federal(db):
    return db.query(TaxBracket).filter(TaxBracket.jurisdiction == "federal").all()


def test_tax_is_progressive_not_flat(db):
    # 60,000 = 50,000 @ 10% + 10,000 @ 20% = 7,000 (a flat 20% would be 12,000)
    tax, marginal = tax_on_income(_federal(db), 60_000)
    assert tax == pytest.approx(7_000)
    assert marginal == pytest.approx(0.20)


def test_income_below_first_bracket_top(db):
    tax, marginal = tax_on_income(_federal(db), 20_000)
    assert tax == pytest.approx(2_000)
    assert marginal == pytest.approx(0.10)


def test_top_open_ended_bracket(db):
    # 50k@10% + 50k@20% + 20k@30% = 5,000 + 10,000 + 6,000
    tax, marginal = tax_on_income(_federal(db), 120_000)
    assert tax == pytest.approx(21_000)
    assert marginal == pytest.approx(0.30)


def test_zero_and_negative_income_owe_nothing(db):
    assert tax_on_income(_federal(db), 0) == (0.0, 0.0)
    assert tax_on_income(_federal(db), -500) == (0.0, 0.0)


def test_no_brackets_is_safe():
    assert tax_on_income([], 80_000) == (0.0, 0.0)


def test_marginal_bracket_reports_the_band(db):
    hit = marginal_bracket(_federal(db), 60_000)
    assert hit is not None
    assert hit.rate == pytest.approx(0.20)
    assert hit.lower_bound == pytest.approx(50_000)
    assert hit.upper_bound == pytest.approx(100_000)


# --- combined estimate --------------------------------------------------------


def test_basic_personal_amount_is_applied(db):
    result = estimate_tax(db, YEAR, 40_000)
    # Taxable after the 10,000 BPA is 30,000 in both jurisdictions.
    assert result["federal_tax"] == pytest.approx(3_000)
    assert result["provincial_tax"] == pytest.approx(1_500)
    assert result["total_tax"] == pytest.approx(4_500)
    # Average rate is against gross, so it is lower than the marginal rate.
    assert result["average_rate"] == pytest.approx(4_500 / 40_000)
    assert result["marginal_rate"] == pytest.approx(0.15)


def test_rrsp_deduction_lowers_taxable_income(db):
    plain = estimate_tax(db, YEAR, 80_000)
    with_rrsp = estimate_tax(db, YEAR, 80_000, rrsp_deduction=10_000)
    assert with_rrsp["taxable_income"] == pytest.approx(70_000)
    assert with_rrsp["total_tax"] < plain["total_tax"]
    # The saving is the marginal rate on the contribution: 10,000 @ (20% + 10%).
    assert plain["total_tax"] - with_rrsp["total_tax"] == pytest.approx(3_000)


def test_income_under_the_bpa_owes_nothing(db):
    result = estimate_tax(db, YEAR, 8_000)
    assert result["total_tax"] == pytest.approx(0)


def test_missing_rates_report_unavailable_rather_than_guessing():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    empty = sessionmaker(bind=engine)()
    assert estimate_tax(empty, YEAR, 80_000) == {"available": False}
    assert rrsp_room(empty, YEAR, 80_000) == {"available": False}
    empty.close()


def test_unknown_year_falls_back_to_stored_rates(db):
    # A January stub in a year whose rates aren't entered yet should still
    # produce an estimate rather than a blank page.
    result = estimate_tax(db, YEAR + 5, 40_000)
    assert result["available"] is True
    assert result["tax_year"] == YEAR


# --- RRSP room ----------------------------------------------------------------


def test_rrsp_room_is_a_share_of_earned_income(db):
    room = rrsp_room(db, YEAR, earned_income=100_000)
    assert room["generated"] == pytest.approx(18_000)
    assert room["room"] == pytest.approx(18_000)
    assert room["capped_by_limit"] is False


def test_rrsp_room_is_capped_by_the_dollar_limit(db):
    room = rrsp_room(db, YEAR, earned_income=500_000)
    assert room["generated"] == pytest.approx(30_000)
    assert room["capped_by_limit"] is True


def test_pension_adjustment_reduces_room_and_carry_forward_adds(db):
    room = rrsp_room(
        db,
        YEAR,
        earned_income=100_000,
        pension_adjustment=5_000,
        carry_forward=2_000,
    )
    assert room["room"] == pytest.approx(15_000)


def test_room_never_goes_negative(db):
    room = rrsp_room(db, YEAR, earned_income=10_000, pension_adjustment=50_000)
    assert room["room"] == 0.0


# --- pay stub parsing ---------------------------------------------------------

# Fabricated stub in a common two-column (current | YTD) layout.
SAMPLE_STUB = """
SAMPLE EMPLOYER INC.
Statement of Earnings
Pay Date: 2099-03-15
Pay Period Ending: 2099-03-08

                          Current        YTD
Gross Pay               3,200.00     19,200.00
Income Tax                640.00      3,840.00
CPP                       180.00      1,080.00
EI                         52.00        312.00
Group RRSP                160.00        960.00
Union Dues                 28.00        168.00
Employer RRSP Match       160.00        960.00
Net Pay                 2,140.00     12,840.00
"""


def _lines(text: str) -> list[str]:
    return text.strip().splitlines()


def test_paystub_reads_current_period_not_ytd():
    draft = parse_lines(_lines(SAMPLE_STUB))
    assert draft.gross_pay == 3_200.00
    assert draft.income_tax == 640.00
    assert draft.net_pay == 2_140.00


def test_paystub_reads_each_deduction():
    draft = parse_lines(_lines(SAMPLE_STUB))
    assert draft.cpp == 180.00
    assert draft.ei == 52.00
    assert draft.rrsp_employee == 160.00
    assert draft.union_dues == 28.00


def test_employer_match_is_not_mistaken_for_an_employee_rrsp():
    draft = parse_lines(_lines(SAMPLE_STUB))
    assert draft.employer_rrsp == 160.00
    assert draft.rrsp_employee == 160.00  # the employee line, read separately


def test_paystub_reads_the_pay_date():
    draft = parse_lines(_lines(SAMPLE_STUB))
    assert draft.pay_date == date(2099, 3, 15)


def test_amounts_reconcile_with_no_leftover():
    draft = parse_lines(_lines(SAMPLE_STUB))
    # 3200 - (640 + 180 + 52 + 160 + 28) - 2140 = 0
    assert draft.other_deductions == 0.0
    assert draft.warnings == []


def test_unexplained_gap_becomes_other_deductions():
    stub = """
    Pay Date: 2099-04-15
    Gross Pay 2,000.00
    Income Tax 400.00
    Net Pay 1,500.00
    """
    draft = parse_lines(_lines(stub))
    assert draft.other_deductions == 100.00


def test_missing_fields_warn_instead_of_being_invented():
    draft = parse_lines(_lines("SAMPLE EMPLOYER INC.\nSome unrelated text"))
    assert draft.gross_pay == 0
    assert draft.net_pay == 0
    assert len(draft.warnings) == 3  # gross, net, pay date
    assert any("gross pay" in w.lower() for w in draft.warnings)


# --- year-to-date summary -----------------------------------------------------


def _add_stubs(db, count=2, **overrides):
    from app.models import PayStub

    db.query(PayStub).delete()
    fields = {"employer": "Sample Co", "gross_pay": 4000, "income_tax": 800, "net_pay": 3000}
    fields.update(overrides)
    for i in range(count):
        db.add(PayStub(pay_date=date(YEAR, 1, 3) + timedelta(days=14 * i), **fields))
    db.commit()


def _summary(db, carry_forward=0.0):
    return payroll_summary(year=YEAR, carry_forward=carry_forward, db=db)


def test_summary_annualizes_from_the_actual_pay_cadence(db):
    _add_stubs(db, count=3)  # 14 days apart
    s = _summary(db)
    assert s.ytd_gross == 12_000
    assert s.annualized_gross == pytest.approx(4_000 * 365 / 14, abs=1)
    assert "14 days apart" in s.projection_basis


def test_single_stub_says_it_assumed_biweekly(db):
    _add_stubs(db, count=1)
    s = _summary(db)
    assert s.annualized_gross == pytest.approx(4_000 * 26)
    assert "assumed biweekly" in s.projection_basis


def test_summary_with_no_stubs_reports_nothing_rather_than_zero_income(db):
    s = _summary(db)
    assert s.stub_count == 0
    assert s.annualized_gross == 0
    assert s.withholding_delta is None
    assert "No pay stubs" in s.projection_basis


def test_employer_rrsp_match_uses_room_but_is_not_a_pension_adjustment(db):
    """A group RRSP match lands in the RRSP, so it spends contribution room.
    Only a registered *pension* plan generates a pension adjustment, which
    shrinks the room itself. Mixing the two up double-counts the match
    against the household."""
    _add_stubs(db, count=2, employer_rrsp=200)
    with_match = _summary(db)

    assert with_match.rrsp["pension_adjustment"] == 0.0
    assert with_match.ytd_rrsp == 0.0  # nothing came off the pay
    assert with_match.ytd_rrsp_contributed == 400.0  # but room was used
    room = with_match.rrsp["room"]
    assert with_match.tax_if_rrsp_maxed["additional_contribution"] == pytest.approx(
        room - 400.0, abs=0.01
    )

    # Same dollars into a pension instead: now the room itself shrinks.
    _add_stubs(db, count=2, employer_pension=200)
    with_pension = _summary(db)
    assert with_pension.rrsp["pension_adjustment"] > 0
    assert with_pension.ytd_rrsp_contributed == 0.0
    assert with_pension.rrsp["room"] < room


def test_pension_adjustment_is_projected_like_the_income(db):
    # Two stubs into the year, both income and the adjustment must be scaled
    # to a full year — otherwise January shows almost no adjustment against a
    # full year of income and overstates the room.
    _add_stubs(db, count=2, employer_pension=200)
    s = _summary(db)
    ratio = s.annualized_gross / s.ytd_gross
    assert s.rrsp["pension_adjustment"] == pytest.approx(400 * ratio, abs=0.01)


def test_carry_forward_room_is_added(db):
    _add_stubs(db, count=2)
    base = _summary(db).rrsp["room"]
    assert _summary(db, carry_forward=5_000).rrsp["room"] == pytest.approx(base + 5_000)


def test_over_withholding_shows_as_a_positive_delta(db):
    _add_stubs(db, count=2, income_tax=3_000)  # deliberately far too much
    assert _summary(db).withholding_delta > 0
    _add_stubs(db, count=2, income_tax=1)
    assert _summary(db).withholding_delta < 0


def test_alternate_labels_and_date_format():
    stub = """
    Payment Date: March 15, 2099
    Total Earnings $1,500.00
    Federal Tax $250.00
    Canada Pension Plan $80.00
    Employment Insurance $25.00
    Net Deposit $1,145.00
    """
    draft = parse_lines(_lines(stub))
    assert draft.gross_pay == 1_500.00
    assert draft.income_tax == 250.00
    assert draft.cpp == 80.00
    assert draft.ei == 25.00
    assert draft.net_pay == 1_145.00
    assert draft.pay_date == date(2099, 3, 15)
