"""Progressive tax math and RRSP room.

Rates live in the database (TaxBracket / TaxYearSetting), not in code, so
they can be corrected when the CRA indexes them — the seeded values are a
starting point, not an authority. Everything here is an *estimate* of
withholding position and contribution room; it is not tax advice and
ignores credits beyond the basic personal amount, other income, spousal
transfers, and provincial surtaxes.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import TaxBracket, TaxYearSetting


@dataclass
class BracketHit:
    jurisdiction: str
    rate: float
    lower_bound: float
    upper_bound: float | None


def tax_on_income(
    brackets: list[TaxBracket], taxable_income: float
) -> tuple[float, float]:
    """Returns (tax owed, marginal rate) for a progressive bracket set."""
    if taxable_income <= 0 or not brackets:
        return 0.0, 0.0
    ordered = sorted(brackets, key=lambda b: float(b.lower_bound))
    tax = 0.0
    marginal = 0.0
    for b in ordered:
        lower = float(b.lower_bound)
        upper = float(b.upper_bound) if b.upper_bound is not None else None
        if taxable_income <= lower:
            break
        span_top = taxable_income if upper is None else min(taxable_income, upper)
        tax += (span_top - lower) * float(b.rate)
        marginal = float(b.rate)
    return tax, marginal


def marginal_bracket(
    brackets: list[TaxBracket], taxable_income: float
) -> BracketHit | None:
    ordered = sorted(brackets, key=lambda b: float(b.lower_bound))
    hit = None
    for b in ordered:
        if taxable_income > float(b.lower_bound):
            hit = b
    if hit is None:
        return None
    return BracketHit(
        jurisdiction=hit.jurisdiction,
        rate=float(hit.rate),
        lower_bound=float(hit.lower_bound),
        upper_bound=float(hit.upper_bound) if hit.upper_bound is not None else None,
    )


def get_tax_year_setting(db: Session, tax_year: int) -> TaxYearSetting | None:
    setting = (
        db.query(TaxYearSetting).filter(TaxYearSetting.tax_year == tax_year).first()
    )
    if setting is not None:
        return setting
    # Fall back to the most recent year we have rates for, so a January
    # pay stub doesn't blank the whole page before rates are entered.
    return db.query(TaxYearSetting).order_by(TaxYearSetting.tax_year.desc()).first()


def brackets_for(db: Session, tax_year: int, jurisdiction: str) -> list[TaxBracket]:
    rows = (
        db.query(TaxBracket)
        .filter(TaxBracket.tax_year == tax_year, TaxBracket.jurisdiction == jurisdiction)
        .all()
    )
    if rows:
        return rows
    latest = (
        db.query(TaxBracket)
        .filter(TaxBracket.jurisdiction == jurisdiction)
        .order_by(TaxBracket.tax_year.desc())
        .first()
    )
    if latest is None:
        return []
    return (
        db.query(TaxBracket)
        .filter(
            TaxBracket.tax_year == latest.tax_year,
            TaxBracket.jurisdiction == jurisdiction,
        )
        .all()
    )


def estimate_tax(
    db: Session, tax_year: int, annual_gross: float, rrsp_deduction: float = 0.0
) -> dict:
    """Estimate combined federal + provincial tax on an annualized income.

    RRSP contributions reduce taxable income, which is exactly the lever
    the household wants to see the effect of.
    """
    setting = get_tax_year_setting(db, tax_year)
    if setting is None:
        return {"available": False}

    province = setting.province
    federal = brackets_for(db, tax_year, "federal")
    provincial = brackets_for(db, tax_year, province)
    if not federal or not provincial:
        return {"available": False}

    taxable = max(0.0, annual_gross - rrsp_deduction)

    fed_taxable = max(0.0, taxable - float(setting.federal_basic_personal_amount))
    prov_taxable = max(0.0, taxable - float(setting.provincial_basic_personal_amount))

    fed_tax, fed_marginal = tax_on_income(federal, fed_taxable)
    prov_tax, prov_marginal = tax_on_income(provincial, prov_taxable)

    total_tax = fed_tax + prov_tax
    combined_marginal = fed_marginal + prov_marginal

    return {
        "available": True,
        "tax_year": setting.tax_year,
        "province": province,
        "annual_gross": round(annual_gross, 2),
        "rrsp_deduction": round(rrsp_deduction, 2),
        "taxable_income": round(taxable, 2),
        "federal_tax": round(fed_tax, 2),
        "provincial_tax": round(prov_tax, 2),
        "total_tax": round(total_tax, 2),
        "marginal_rate": round(combined_marginal, 4),
        "average_rate": round(total_tax / annual_gross, 4) if annual_gross > 0 else 0.0,
        "federal_bracket": marginal_bracket(federal, fed_taxable),
        "provincial_bracket": marginal_bracket(provincial, prov_taxable),
    }


def rrsp_room(
    db: Session,
    tax_year: int,
    earned_income: float,
    pension_adjustment: float = 0.0,
    carry_forward: float = 0.0,
) -> dict:
    """New RRSP room generated by this year's earned income.

    Real CRA room is prior-year earned income × rate, capped, minus the
    pension adjustment, plus carry-forward from your Notice of
    Assessment. This models the formula but can only see what's been
    entered here — so it's labeled an estimate and the carry-forward is
    the user's to supply.
    """
    setting = get_tax_year_setting(db, tax_year)
    if setting is None:
        return {"available": False}

    rate = float(setting.rrsp_rate)
    limit = float(setting.rrsp_dollar_limit)
    generated = min(earned_income * rate, limit)
    room = max(0.0, generated - pension_adjustment + carry_forward)
    return {
        "available": True,
        "tax_year": setting.tax_year,
        "rate": rate,
        "dollar_limit": limit,
        "earned_income": round(earned_income, 2),
        "generated": round(generated, 2),
        "pension_adjustment": round(pension_adjustment, 2),
        "carry_forward": round(carry_forward, 2),
        "room": round(room, 2),
        "capped_by_limit": earned_income * rate > limit,
    }
