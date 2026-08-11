from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import PayStub, TaxBracket
from app.parsers.paystub import parse_paystub_pdf
from app.schemas import (
    PayrollSummary,
    PayStubCreate,
    PayStubDraftOut,
    PayStubOut,
    TaxBracketOut,
    TaxBracketsReplace,
    TaxSettingOut,
)
from app.taxcalc import estimate_tax, get_tax_year_setting, rrsp_room

router = APIRouter(prefix="/payroll", tags=["payroll"])

_MAX_UPLOAD_BYTES = 20 * 1024 * 1024

RATES_NOTE = (
    "Estimates only, based on the tax rates stored in this app. Rates are "
    "indexed every year — check them against canada.ca and your province, "
    "and edit below if they're out of date. Not tax advice: this ignores "
    "credits beyond the basic personal amount, other income, and spousal "
    "transfers."
)


def _to_out(stub: PayStub) -> PayStubOut:
    deductions = (
        float(stub.income_tax)
        + float(stub.cpp)
        + float(stub.ei)
        + float(stub.rrsp_employee)
        + float(stub.pension_employee)
        + float(stub.union_dues)
        + float(stub.other_deductions)
    )
    return PayStubOut(
        id=stub.id,
        employer=stub.employer,
        earner=stub.earner,
        pay_date=stub.pay_date,
        period_start=stub.period_start,
        period_end=stub.period_end,
        gross_pay=float(stub.gross_pay),
        income_tax=float(stub.income_tax),
        cpp=float(stub.cpp),
        ei=float(stub.ei),
        rrsp_employee=float(stub.rrsp_employee),
        pension_employee=float(stub.pension_employee),
        union_dues=float(stub.union_dues),
        other_deductions=float(stub.other_deductions),
        net_pay=float(stub.net_pay),
        employer_rrsp=float(stub.employer_rrsp),
        employer_pension=float(stub.employer_pension),
        notes=stub.notes,
        total_deductions=round(deductions, 2),
    )


@router.post("/preview", response_model=PayStubDraftOut)
async def preview_paystub(file: UploadFile = File(...), db: Session = Depends(get_db)):
    filename = (file.filename or "").lower()
    if not filename.endswith(".pdf") and file.content_type != "application/pdf":
        raise HTTPException(400, "Pay stubs must be PDF files")
    raw = await file.read()
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(400, "File too large")

    draft = parse_paystub_pdf(raw)
    return PayStubDraftOut(
        employer=draft.employer,
        pay_date=draft.pay_date,
        period_start=draft.period_start,
        period_end=draft.period_end,
        gross_pay=draft.gross_pay,
        income_tax=draft.income_tax,
        cpp=draft.cpp,
        ei=draft.ei,
        rrsp_employee=draft.rrsp_employee,
        pension_employee=draft.pension_employee,
        union_dues=draft.union_dues,
        other_deductions=draft.other_deductions,
        net_pay=draft.net_pay,
        employer_rrsp=draft.employer_rrsp,
        employer_pension=draft.employer_pension,
        warnings=draft.warnings,
        matched_fields=draft.matched_fields,
    )


@router.get("/stubs", response_model=list[PayStubOut])
def list_stubs(year: int | None = None, db: Session = Depends(get_db)):
    query = db.query(PayStub)
    if year:
        query = query.filter(
            PayStub.pay_date >= f"{year:04d}-01-01",
            PayStub.pay_date < f"{year + 1:04d}-01-01",
        )
    return [_to_out(s) for s in query.order_by(PayStub.pay_date.desc()).all()]


@router.post("/stubs", response_model=PayStubOut)
def create_stub(payload: PayStubCreate, db: Session = Depends(get_db)):
    if payload.gross_pay <= 0:
        raise HTTPException(400, "Gross pay is required")
    stub = PayStub(**payload.model_dump())
    db.add(stub)
    db.commit()
    db.refresh(stub)
    return _to_out(stub)


@router.delete("/stubs/{stub_id}")
def delete_stub(stub_id: int, db: Session = Depends(get_db)):
    stub = db.get(PayStub, stub_id)
    if stub is None:
        raise HTTPException(404, "Pay stub not found")
    db.delete(stub)
    db.commit()
    return {"ok": True}


@router.get("/summary", response_model=PayrollSummary)
def payroll_summary(
    year: int | None = None,
    carry_forward: float = 0.0,
    db: Session = Depends(get_db),
):
    year = year or date.today().year
    stubs = (
        db.query(PayStub)
        .filter(
            PayStub.pay_date >= f"{year:04d}-01-01",
            PayStub.pay_date < f"{year + 1:04d}-01-01",
        )
        .order_by(PayStub.pay_date)
        .all()
    )

    def total(attr: str) -> float:
        return round(sum(float(getattr(s, attr)) for s in stubs), 2)

    ytd_gross = total("gross_pay")
    ytd_rrsp = total("rrsp_employee")
    ytd_pension = total("pension_employee")
    ytd_income_tax = total("income_tax")

    # Annualize from the stubs' own cadence rather than assuming biweekly:
    # count pay periods and scale by how much of the year they cover.
    if stubs and ytd_gross > 0:
        first, last = stubs[0].pay_date, stubs[-1].pay_date
        if len(stubs) == 1:
            annualized = ytd_gross * 26  # single stub: assume biweekly
            basis = "1 stub, assumed biweekly (26 periods)"
        else:
            span_days = max((last - first).days, 1)
            avg_gap = span_days / (len(stubs) - 1)
            periods_per_year = 365.0 / avg_gap
            annualized = (ytd_gross / len(stubs)) * periods_per_year
            basis = (
                f"{len(stubs)} stubs averaging {avg_gap:.0f} days apart "
                f"(~{periods_per_year:.0f} pay periods/year)"
            )
    else:
        annualized = 0.0
        basis = "No pay stubs entered yet"

    tax = estimate_tax(db, year, annualized, rrsp_deduction=ytd_rrsp)

    # Pension adjustment approximation. Only registered pension plan
    # contributions (yours + your employer's) generate a PA and shrink RRSP
    # room; an employer *group RRSP* match does not — that money lands in the
    # RRSP itself, so it counts as a contribution against the room below
    # rather than as an adjustment to it.
    #
    # Projected to a full year on the same basis as the income above: pairing
    # an annualized income with a year-to-date adjustment would overstate the
    # room in January and understate it in December.
    pa_to_date = ytd_pension + total("employer_pension")
    projection = (annualized / ytd_gross) if ytd_gross > 0 else 1.0
    pension_adjustment = pa_to_date * projection
    rrsp = rrsp_room(
        db,
        year,
        earned_income=annualized,
        pension_adjustment=pension_adjustment,
        carry_forward=carry_forward,
    )

    # Room already used this year: what came off your pay plus the employer's
    # match, since both are deposited into the RRSP.
    ytd_rrsp_contributed = round(ytd_rrsp + total("employer_rrsp"), 2)

    tax_if_maxed = None
    if tax.get("available") and rrsp.get("available"):
        remaining_room = max(0.0, rrsp["room"] - ytd_rrsp_contributed)
        if remaining_room > 0:
            tax_if_maxed = estimate_tax(
                db, year, annualized, rrsp_deduction=ytd_rrsp + remaining_room
            )
            tax_if_maxed["additional_contribution"] = round(remaining_room, 2)
            tax_if_maxed["tax_saving"] = round(
                tax["total_tax"] - tax_if_maxed["total_tax"], 2
            )

    withholding_delta = None
    if tax.get("available") and ytd_gross > 0 and annualized > 0:
        # Expected tax withheld so far if withholding tracked the estimate.
        expected_to_date = tax["total_tax"] * (ytd_gross / annualized)
        withholding_delta = round(ytd_income_tax - expected_to_date, 2)

    return PayrollSummary(
        tax_year=year,
        stub_count=len(stubs),
        ytd_gross=ytd_gross,
        ytd_income_tax=ytd_income_tax,
        ytd_cpp=total("cpp"),
        ytd_ei=total("ei"),
        ytd_rrsp=ytd_rrsp,
        ytd_rrsp_contributed=ytd_rrsp_contributed,
        ytd_employer_rrsp=total("employer_rrsp"),
        ytd_pension=ytd_pension,
        ytd_other_deductions=total("other_deductions") + total("union_dues"),
        ytd_net=total("net_pay"),
        annualized_gross=round(annualized, 2),
        projection_basis=basis,
        tax=tax,
        tax_if_rrsp_maxed=tax_if_maxed,
        rrsp=rrsp,
        withholding_delta=withholding_delta,
        rates_verified_note=RATES_NOTE,
    )


@router.get("/tax-brackets", response_model=list[TaxBracketOut])
def list_brackets(year: int | None = None, db: Session = Depends(get_db)):
    query = db.query(TaxBracket)
    if year:
        query = query.filter(TaxBracket.tax_year == year)
    return query.order_by(
        TaxBracket.tax_year, TaxBracket.jurisdiction, TaxBracket.lower_bound
    ).all()


@router.put("/tax-brackets", response_model=list[TaxBracketOut])
def replace_brackets(payload: TaxBracketsReplace, db: Session = Depends(get_db)):
    if not payload.brackets:
        raise HTTPException(400, "At least one bracket is required")
    for b in payload.brackets:
        if b.rate < 0 or b.rate > 1:
            raise HTTPException(400, "Rate must be a fraction between 0 and 1")
    db.query(TaxBracket).filter(
        TaxBracket.tax_year == payload.tax_year,
        TaxBracket.jurisdiction == payload.jurisdiction,
    ).delete()
    for b in payload.brackets:
        db.add(
            TaxBracket(
                tax_year=payload.tax_year,
                jurisdiction=payload.jurisdiction,
                lower_bound=b.lower_bound,
                upper_bound=b.upper_bound,
                rate=b.rate,
            )
        )
    db.commit()
    return (
        db.query(TaxBracket)
        .filter(
            TaxBracket.tax_year == payload.tax_year,
            TaxBracket.jurisdiction == payload.jurisdiction,
        )
        .order_by(TaxBracket.lower_bound)
        .all()
    )


@router.get("/tax-settings", response_model=TaxSettingOut | None)
def tax_settings(year: int | None = None, db: Session = Depends(get_db)):
    return get_tax_year_setting(db, year or date.today().year)
