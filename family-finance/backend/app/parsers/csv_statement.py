"""Parser for CSV transaction exports.

Handles two common shapes by sniffing the header row:

1. Ledger style (like the household's own tracking sheet):
   Card, Date, Category, Transaction Details, Funds Out, Funds In
2. Bank-export style:
   Date, Description, Amount   (or Debit/Credit column pairs)

Column detection is heuristic (case-insensitive header matching) so minor
naming differences between banks still work. Sign convention matches the
rest of the app: positive = money out, negative = money in. Rows that can't
be parsed are surfaced as warnings, never silently dropped.
"""

import csv
import io
import re
from datetime import date, datetime

from .base import ParseResult, RawTransaction

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%m/%d/%y",
    "%d %b %Y",
    "%d %b. %Y",
    "%d-%b-%Y",
    "%b %d, %Y",
    "%Y/%m/%d",
)

_MONEY_JUNK = re.compile(r"[$,\s]")


def _parse_date(raw: str) -> date | None:
    cleaned = raw.strip()
    if not cleaned:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def _parse_money(raw: str) -> float | None:
    cleaned = _MONEY_JUNK.sub("", raw or "")
    if not cleaned:
        return None
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    if negative:
        cleaned = cleaned[1:-1]
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return -value if negative else value


def _find_column(headers: list[str], *needles: str, exclude: tuple[str, ...] = ()) -> int | None:
    for i, header in enumerate(headers):
        if any(x in header for x in exclude):
            continue
        if any(needle in header for needle in needles):
            return i
    return None


def parse_csv_statement(raw_bytes: bytes) -> ParseResult:
    result = ParseResult()
    # utf-8-sig strips the BOM Excel prepends to CSV exports.
    text = raw_bytes.decode("utf-8-sig", errors="replace")

    try:
        dialect = csv.Sniffer().sniff(text[:2048], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel

    rows = list(csv.reader(io.StringIO(text), dialect))
    rows = [r for r in rows if any(cell.strip() for cell in r)]
    if not rows:
        result.warnings.append("The CSV file is empty.")
        return result

    headers = [cell.strip().lower() for cell in rows[0]]

    date_col = _find_column(headers, "date", exclude=("post",))
    post_date_col = _find_column(headers, "post date", "posting date")
    desc_col = _find_column(headers, "description", "details", "merchant", "payee", "memo", "narrative")
    category_col = _find_column(headers, "category")
    amount_col = _find_column(headers, "amount")
    out_col = _find_column(headers, "funds out", "money out", "debit", "withdrawal", "expense")
    in_col = _find_column(headers, "funds in", "money in", "credit", "deposit", "income", "refund")

    if date_col is None or desc_col is None or (amount_col is None and out_col is None and in_col is None):
        result.warnings.append(
            "Could not recognize the CSV columns. Needs a date column, a "
            "description/details column, and either an amount column or "
            "funds out / funds in columns."
        )
        return result

    for line_no, row in enumerate(rows[1:], start=2):
        def cell(idx: int | None) -> str:
            return row[idx].strip() if idx is not None and idx < len(row) else ""

        trans_date = _parse_date(cell(date_col))
        if trans_date is None:
            result.warnings.append(f"Line {line_no}: unrecognized date {cell(date_col)!r} — row skipped.")
            continue

        description = cell(desc_col)
        if not description:
            result.warnings.append(f"Line {line_no}: empty description — row skipped.")
            continue

        if amount_col is not None:
            amount = _parse_money(cell(amount_col))
            if amount is None:
                result.warnings.append(f"Line {line_no}: unrecognized amount {cell(amount_col)!r} — row skipped.")
                continue
        else:
            out_amount = _parse_money(cell(out_col)) if out_col is not None else None
            in_amount = _parse_money(cell(in_col)) if in_col is not None else None
            if out_amount is None and in_amount is None:
                result.warnings.append(f"Line {line_no}: no amount in funds out/in columns — row skipped.")
                continue
            amount = (out_amount or 0.0) - (in_amount or 0.0)

        result.transactions.append(
            RawTransaction(
                trans_date=trans_date,
                post_date=_parse_date(cell(post_date_col)) if post_date_col is not None else None,
                description=description,
                amount=round(amount, 2),
                category_hint=cell(category_col),
            )
        )

    result.transactions.sort(key=lambda t: t.trans_date)
    return result
