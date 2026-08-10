"""CSV parser tests — all data fabricated, mirroring column layouts only."""

from datetime import date

from app.parsers.csv_statement import parse_csv_statement


def _parse(text: str):
    return parse_csv_statement(text.encode("utf-8"))


LEDGER_CSV = """Card,Date,Category,Transaction Details,Funds Out,Funds In
Sample Bank,2026-07-02,Grocery,SAMPLE SUPERMARKET,"$1,180.61",
Sample Bank,2026-07-04,Rental Income,E-TRANSFER RECEIVE TENANT,,500.00
Sample Bank,09/15/2026,Payroll,PAYROLL DEPOSIT SAMPLE CORP,,1680.82
Sample Bank,2026-07-03,Dine out,SAMPLE RESTAURANT,35.00,
"""


def test_ledger_style_columns():
    result = _parse(LEDGER_CSV)
    assert len(result.transactions) == 4
    assert result.warnings == []


def test_funds_out_positive_funds_in_negative():
    result = _parse(LEDGER_CSV)
    grocery = next(t for t in result.transactions if "SUPERMARKET" in t.description)
    rental = next(t for t in result.transactions if "TENANT" in t.description)
    assert grocery.amount == 1180.61  # money out, comma+$ cleaned
    assert rental.amount == -500.00  # money in


def test_category_hint_carried():
    result = _parse(LEDGER_CSV)
    grocery = next(t for t in result.transactions if "SUPERMARKET" in t.description)
    assert grocery.category_hint == "Grocery"


def test_mixed_date_formats():
    result = _parse(LEDGER_CSV)
    payroll = next(t for t in result.transactions if "PAYROLL" in t.description)
    assert payroll.trans_date == date(2026, 9, 15)


def test_sorted_by_date():
    result = _parse(LEDGER_CSV)
    dates = [t.trans_date for t in result.transactions]
    assert dates == sorted(dates)


def test_simple_bank_export_with_amount_column():
    csv_text = """Date,Description,Amount
2026-07-01,COFFEE SHOP,4.50
2026-07-02,REFUND FROM STORE,(12.00)
"""
    result = _parse(csv_text)
    assert len(result.transactions) == 2
    assert result.transactions[0].amount == 4.50
    assert result.transactions[1].amount == -12.00  # parentheses = negative


def test_bad_rows_warn_but_do_not_stop_parsing():
    csv_text = """Date,Description,Amount
not-a-date,SOMETHING,10.00
2026-07-01,GOOD ROW,5.00
2026-07-02,,7.00
2026-07-03,NO AMOUNT,abc
"""
    result = _parse(csv_text)
    assert len(result.transactions) == 1
    assert result.transactions[0].description == "GOOD ROW"
    assert len(result.warnings) == 3


def test_unrecognizable_columns_produce_clear_warning():
    result = _parse("Foo,Bar\n1,2\n")
    assert result.transactions == []
    assert any("Could not recognize" in w for w in result.warnings)


def test_empty_file():
    result = _parse("")
    assert result.transactions == []
    assert any("empty" in w.lower() for w in result.warnings)
