"""Starting-point tax rates.

IMPORTANT: these are seeded defaults for convenience, NOT an authoritative
source. Federal and provincial brackets, the basic personal amounts, and
the RRSP dollar limit are all indexed and change every year — and mid-year
rate changes happen too. They are stored in the database precisely so the
household can correct them from the Payroll page after checking
canada.ca / their province, without touching code. Seeding only ever fills
an empty year; it never overwrites edited values.

Values below are 2025 Canada (federal) and Manitoba figures.
"""

from sqlalchemy.orm import Session

from app.models import TaxBracket, TaxYearSetting

SEED_YEAR = 2025

FEDERAL_BRACKETS_2025 = [
    (0, 57_375, 0.145),
    (57_375, 114_750, 0.205),
    (114_750, 177_882, 0.26),
    (177_882, 253_414, 0.29),
    (253_414, None, 0.33),
]

MANITOBA_BRACKETS_2025 = [
    (0, 47_564, 0.108),
    (47_564, 101_200, 0.1275),
    (101_200, None, 0.174),
]

SETTINGS_2025 = {
    "rrsp_rate": 0.18,
    "rrsp_dollar_limit": 32_490.0,
    "federal_basic_personal_amount": 16_129.0,
    "provincial_basic_personal_amount": 15_969.0,
    "province": "MB",
}


def seed_tax_data(db: Session) -> None:
    existing_years = {
        row[0] for row in db.query(TaxBracket.tax_year).distinct().all()
    }
    changed = False

    if SEED_YEAR not in existing_years:
        for lower, upper, rate in FEDERAL_BRACKETS_2025:
            db.add(
                TaxBracket(
                    tax_year=SEED_YEAR,
                    jurisdiction="federal",
                    lower_bound=lower,
                    upper_bound=upper,
                    rate=rate,
                )
            )
        for lower, upper, rate in MANITOBA_BRACKETS_2025:
            db.add(
                TaxBracket(
                    tax_year=SEED_YEAR,
                    jurisdiction="MB",
                    lower_bound=lower,
                    upper_bound=upper,
                    rate=rate,
                )
            )
        changed = True

    if (
        db.query(TaxYearSetting).filter(TaxYearSetting.tax_year == SEED_YEAR).first()
        is None
    ):
        db.add(TaxYearSetting(tax_year=SEED_YEAR, **SETTINGS_2025))
        changed = True

    if changed:
        db.commit()
