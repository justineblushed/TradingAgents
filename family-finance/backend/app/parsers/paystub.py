"""Best-effort pay stub extraction.

Pay stub layouts vary wildly between employers and payroll providers, so
this makes no attempt at a universal parse. It scans the text for known
labels and takes a nearby currency amount, producing a *pre-filled draft*
that the user reviews and corrects before anything is saved. Every field
it can't find is simply left at zero rather than guessed.

Where a stub shows both a current and a year-to-date column, the first
amount on the line is treated as the current period and the last as YTD —
the near-universal convention. When only one amount is present it's
treated as the current period.
"""

import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime

_AMOUNT = re.compile(r"-?\$?\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})|-?\$?\s?\d+\.\d{2}")

_DATE_PATTERNS = (
    (re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"), "%Y-%m-%d"),
    (re.compile(r"\b(\d{2}/\d{2}/\d{4})\b"), "%m/%d/%Y"),
    (re.compile(r"\b(\d{1,2}\s+[A-Za-z]{3,9}\.?\s+\d{4})\b"), None),
    (re.compile(r"\b([A-Za-z]{3,9}\s+\d{1,2},\s*\d{4})\b"), None),
)

# label -> field. Order matters: more specific labels first, since a line
# reading "Employer RRSP" must not be captured by the plain "rrsp" rule.
_FIELD_LABELS: list[tuple[str, tuple[str, ...]]] = [
    ("employer_rrsp", ("employer rrsp", "employer contribution rrsp", "rrsp match", "employer match")),
    ("employer_pension", ("employer pension", "pension - employer", "employer pens")),
    ("gross_pay", ("gross pay", "gross earnings", "total earnings", "gross income", "gross")),
    ("income_tax", ("income tax", "federal tax", "tax deduction", "withholding tax", "fed tax")),
    ("cpp", ("cpp", "qpp", "canada pension")),
    ("ei", ("employment insurance", "ei premium", " ei ", "ei ")),
    ("rrsp_employee", ("rrsp", "group rrsp", "retirement savings")),
    ("pension_employee", ("pension", "rpp", "registered pension")),
    ("union_dues", ("union dues", "union")),
    ("net_pay", ("net pay", "net deposit", "take home", "net amount", "deposit amount")),
]


@dataclass
class PayStubDraft:
    employer: str = ""
    pay_date: date | None = None
    period_start: date | None = None
    period_end: date | None = None
    gross_pay: float = 0.0
    income_tax: float = 0.0
    cpp: float = 0.0
    ei: float = 0.0
    rrsp_employee: float = 0.0
    pension_employee: float = 0.0
    union_dues: float = 0.0
    other_deductions: float = 0.0
    net_pay: float = 0.0
    employer_rrsp: float = 0.0
    employer_pension: float = 0.0
    warnings: list[str] = field(default_factory=list)
    matched_fields: list[str] = field(default_factory=list)


def _to_float(raw: str) -> float | None:
    cleaned = raw.replace("$", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_date(text: str) -> date | None:
    for pattern, fmt in _DATE_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        raw = m.group(1)
        if fmt:
            try:
                return datetime.strptime(raw, fmt).date()
            except ValueError:
                continue
        for candidate in ("%d %b %Y", "%d %B %Y", "%d %b. %Y", "%b %d, %Y", "%B %d, %Y"):
            try:
                return datetime.strptime(raw.replace(".", ""), candidate.replace(".", "")).date()
            except ValueError:
                continue
    return None


def parse_lines(lines: list[str]) -> PayStubDraft:
    draft = PayStubDraft()
    claimed: set[str] = set()

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        lowered = f" {line.lower()} "

        if draft.pay_date is None and any(
            k in lowered for k in ("pay date", "payment date", "date of pay", "cheque date")
        ):
            draft.pay_date = _parse_date(line)
        if draft.period_end is None and any(
            k in lowered for k in ("period ending", "pay period", "period end")
        ):
            draft.period_end = _parse_date(line)

        amounts = [
            v for v in (_to_float(m.group()) for m in _AMOUNT.finditer(line)) if v is not None
        ]
        if not amounts:
            continue

        for field_name, labels in _FIELD_LABELS:
            if field_name in claimed:
                continue
            if any(label in lowered for label in labels):
                # First amount on the line = current period (YTD columns
                # come after it on virtually every stub layout).
                setattr(draft, field_name, amounts[0])
                claimed.add(field_name)
                draft.matched_fields.append(field_name)
                break

    if draft.pay_date is None:
        for raw_line in lines:
            found = _parse_date(raw_line)
            if found:
                draft.pay_date = found
                break

    if draft.gross_pay == 0:
        draft.warnings.append(
            "Could not find gross pay — enter it manually below before saving."
        )
    if draft.net_pay == 0:
        draft.warnings.append("Could not find net pay — check the amount below.")
    if draft.pay_date is None:
        draft.warnings.append("Could not find a pay date — pick one below.")

    # Sanity check: the parts should roughly add up. Anything left over is
    # surfaced as "other deductions" rather than silently lost.
    known_deductions = (
        draft.income_tax
        + draft.cpp
        + draft.ei
        + draft.rrsp_employee
        + draft.pension_employee
        + draft.union_dues
    )
    if draft.gross_pay > 0 and draft.net_pay > 0:
        residual = draft.gross_pay - known_deductions - draft.net_pay
        if residual > 0.01:
            draft.other_deductions = round(residual, 2)
        elif residual < -0.01:
            draft.warnings.append(
                "Gross minus deductions is less than net pay — some amounts were "
                "probably read from the wrong column. Please check each field."
            )
    return draft


def parse_paystub_pdf(pdf_bytes: bytes) -> PayStubDraft:
    import pdfplumber

    lines: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            lines.extend((page.extract_text(x_tolerance=1) or "").splitlines())
    return parse_lines(lines)
