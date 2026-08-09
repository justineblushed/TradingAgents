"""Parser for tabular credit-card statement PDFs.

Targets the common Canadian issuer layout: a "Trans Date | Post Date |
Description | Amount ($)" table, with an optional indented
"FOREIGN CURRENCY ..." line following a transaction that was charged in
another currency. Works purely on extracted text — no OCR, no network
calls, nothing leaves the machine running this code.

This format is shared by several issuers beyond the one it was built
against; add a new module under this package (subclassing/mirroring this
one) for banks whose layout differs, and register it in ``PARSERS`` in
``app/parsers/registry.py`` (added when the second format is needed).
"""

import io
import re
from datetime import date

from .base import ParseResult, RawTransaction

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

_TXN_LINE = re.compile(
    r"^(?P<tmon>[A-Za-z]{3})\s+(?P<tday>\d{1,2})\s+"
    r"(?P<pmon>[A-Za-z]{3})\s+(?P<pday>\d{1,2})\s+"
    r"(?P<description>.+?)\s+(?P<amount>-?[\d,]+\.\d{2})$"
)
_FX_LINE = re.compile(
    r"^FOREIGN CURRENCY\s+(?P<currency>[A-Z]{3})\s+(?P<amount>[\d,]+\.\d{2})"
    r"\s+@\s+(?P<rate>[\d.]+)$"
)
_ACCOUNT_LINE = re.compile(r"Account Number\s+[X\s]*(?P<last4>\d{4})")
_STOP_MARKERS = (
    "interest rate chart",
    "balance description",
    "important information",
)
_SKIP_PREFIXES = (
    "account number",
    "trans",
    "post",
    "date",
    "description",
    "card number",
    "transaction details",
    "page ",
)


def _parse_month_day(mon: str, day: str) -> tuple[int, int] | None:
    month = _MONTHS.get(mon.lower()[:3])
    if month is None:
        return None
    return month, int(day)


def _resolve_year(month: int, running_year: int, last_month: int | None) -> int:
    if last_month is not None and month < last_month:
        return running_year + 1
    return running_year


def parse_lines(lines: list[str], statement_year: int) -> ParseResult:
    """Core parsing logic over already-extracted text lines.

    Split out from ``parse_credit_card_statement`` so tests can exercise the
    parsing rules directly with fabricated lines, without needing to render
    an actual PDF (and without ever needing real statement data as a fixture).
    """
    result = ParseResult()
    running_year = statement_year
    last_month: int | None = None
    prev_txn: RawTransaction | None = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        lowered = line.lower()
        if any(lowered.startswith(marker) for marker in _STOP_MARKERS):
            break

        acct_match = _ACCOUNT_LINE.search(line)
        if acct_match and not result.account_last_four:
            result.account_last_four = acct_match.group("last4")

        if any(lowered.startswith(p) for p in _SKIP_PREFIXES):
            continue

        txn_match = _TXN_LINE.match(line)
        if txn_match:
            tmon = _parse_month_day(txn_match["tmon"], txn_match["tday"])
            pmon = _parse_month_day(txn_match["pmon"], txn_match["pday"])
            if tmon is None or pmon is None:
                result.warnings.append(f"Could not parse date in line: {line!r}")
                continue

            running_year = _resolve_year(tmon[0], running_year, last_month)
            last_month = tmon[0]
            trans_date = date(running_year, tmon[0], tmon[1])

            post_year = running_year if pmon[0] >= tmon[0] else running_year + 1
            post_date = date(post_year, pmon[0], pmon[1])

            amount = float(txn_match["amount"].replace(",", ""))
            prev_txn = RawTransaction(
                trans_date=trans_date,
                post_date=post_date,
                description=txn_match["description"].strip(),
                amount=amount,
            )
            result.transactions.append(prev_txn)
            continue

        fx_match = _FX_LINE.match(line)
        if fx_match and prev_txn is not None:
            prev_txn.foreign_currency_note = (
                f"{fx_match['currency']} {fx_match['amount']} @ {fx_match['rate']}"
            )
            continue

        # Unrecognized line inside the transaction table — surface it
        # instead of silently dropping data the user might care about.
        result.warnings.append(f"Unrecognized line skipped: {line!r}")

    return result


def parse_credit_card_statement(pdf_bytes: bytes, statement_year: int) -> ParseResult:
    """Parse a credit-card statement PDF into transactions.

    ``statement_year`` is the calendar year the FIRST transaction on the
    statement falls in (statements don't repeat the year on every line,
    so this must come from the statement's cover page or the filename).
    Year rolls forward automatically when the month number decreases
    (e.g. a Jul 31 statement close continuing into early Aug).
    """
    import pdfplumber

    # Default x_tolerance (3) merges adjacent words with tight kerning in this
    # statement layout (e.g. "BESTWESTERN"); a tighter tolerance restores the
    # word boundaries pdfplumber's own word-segmentation already finds.
    lines: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            lines.extend((page.extract_text(x_tolerance=1) or "").splitlines())

    return parse_lines(lines, statement_year=statement_year)
