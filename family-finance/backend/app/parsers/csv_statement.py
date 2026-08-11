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


def _should_flip_single_amount_column(rows: list[list[str]], amount_col: int) -> bool:
    """Decide whether a single signed "Amount" column uses the opposite sign
    convention from this app's (positive = money out, negative = money in).

    Credit-card exports overwhelmingly follow this app's convention already
    (a charge is positive; refunds are rare). Chequing/savings exports from
    many banks — Simplii among them — follow the ledger convention instead:
    a withdrawal is negative, a deposit positive. There's no column name to
    go on ("Amount" doesn't say which), so this leans on a property that
    holds regardless of bank: in any real statement, spending transactions
    vastly outnumber deposits. If parsing the column at face value would
    make negative amounts the majority, the file is using the ledger
    convention and every amount needs its sign flipped so spending reads
    as positive here too. A tie (or a majority already positive) leaves the
    file alone.
    """
    positive = negative = 0
    for row in rows:
        if amount_col >= len(row):
            continue
        value = _parse_money(row[amount_col])
        if value is None or value == 0:
            continue
        if value > 0:
            positive += 1
        else:
            negative += 1
    return negative > positive


def _infer_headerless_columns(
    rows: list[list[str]],
) -> tuple[int, int, int | None, int | None, int | None] | None:
    """Infer (date, description, amount, out, in) column indexes for a CSV
    with no header row, by looking at what actually parses in each column.

    Convention for two money columns follows the common bank-export order:
    debit (money out) first, credit (money in) second.
    """
    sample = rows[:50]
    n_cols = max(len(r) for r in sample)
    if n_cols < 3:
        return None

    date_col = None
    money_cols: list[int] = []
    text_cols: list[int] = []

    for col in range(n_cols):
        values = [r[col].strip() for r in sample if col < len(r) and r[col].strip()]
        if not values:
            continue
        if all(_parse_date(v) is not None for v in values):
            if date_col is None:
                date_col = col
            continue
        if all(_parse_money(v) is not None for v in values):
            money_cols.append(col)
            continue
        text_cols.append(col)

    if date_col is None or not text_cols or not money_cols:
        return None

    desc_col = text_cols[0]
    if len(money_cols) == 1:
        return date_col, desc_col, money_cols[0], None, None
    return date_col, desc_col, None, money_cols[0], money_cols[1]


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

    data_rows = rows[1:]
    first_line = 2

    if date_col is None or desc_col is None or (amount_col is None and out_col is None and in_col is None):
        # Some bank exports (e.g. CIBC) have no header row at all — the file
        # starts straight with data. Infer columns from content instead.
        inferred = _infer_headerless_columns(rows)
        if inferred is None:
            result.warnings.append(
                "Could not recognize the CSV columns. Needs a date column, a "
                "description/details column, and either an amount column or "
                "funds out / funds in columns (a headerless bank export with "
                "date, description, debit, credit columns also works)."
            )
            return result
        date_col, desc_col, amount_col, out_col, in_col = inferred
        post_date_col = None
        category_col = None
        data_rows = rows
        first_line = 1

    flip_amount_sign = (
        amount_col is not None and _should_flip_single_amount_column(data_rows, amount_col)
    )
    if flip_amount_sign:
        result.warnings.append(
            "This file's Amount column looked like it uses the opposite sign "
            "convention from this app (more withdrawals than deposits came "
            "out negative) — signs were flipped so spending shows as a "
            "positive amount. Check a few rows below before importing; if "
            "something looks backwards, let us know."
        )

    for line_no, row in enumerate(data_rows, start=first_line):
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
            if flip_amount_sign:
                amount = -amount
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
