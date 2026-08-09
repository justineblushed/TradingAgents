"""Parser tests use entirely fabricated data — fake merchants, fake dates,
fake amounts — mirroring the real statement's line structure without ever
touching real personal financial data."""

from app.parsers.creditcard_statement import parse_lines

SAMPLE_LINES = [
    "Account Number XXXX XXXX XXXX 1234 Account Holder: Page 1 of 2",
    "Transaction Details - continued",
    "Trans",
    "Date",
    "Post",
    "Date Description Amount ($)",
    "Card Number XXXX XXXX XXXX 1234",
    "Jul 2 Jul 6 SAMPLE HOTEL ANYTOWN WI 143.14",
    "FOREIGN CURRENCY USD 98.16 @ 1.458231458",
    "Jul 6 Jul 7 PAYMENT, THANK YOU -2,360.60",
    "Jul 10 Jul 13 SAMPLE GROCERY STORE ANYTOWN MB 46.55",
    "Aug 4 Aug 4 CASH INTEREST 0.28",
    "Interest Rate Chart",
    "Balance",
    "Description Daily Rate Annual Rate",
    "PURCHASE 0.060247% 21.99% $0.00",
]


def test_extracts_account_last_four():
    result = parse_lines(SAMPLE_LINES, statement_year=2026)
    assert result.account_last_four == "1234"


def test_parses_expected_transaction_count():
    result = parse_lines(SAMPLE_LINES, statement_year=2026)
    assert len(result.transactions) == 4


def test_attaches_foreign_currency_note_to_preceding_transaction():
    result = parse_lines(SAMPLE_LINES, statement_year=2026)
    hotel = result.transactions[0]
    assert hotel.description == "SAMPLE HOTEL ANYTOWN WI"
    assert hotel.foreign_currency_note == "USD 98.16 @ 1.458231458"


def test_negative_amount_parsed_for_payment():
    result = parse_lines(SAMPLE_LINES, statement_year=2026)
    payment = next(t for t in result.transactions if "PAYMENT" in t.description)
    assert payment.amount == -2360.60


def test_year_rolls_forward_across_month_boundary():
    result = parse_lines(SAMPLE_LINES, statement_year=2026)
    interest = result.transactions[-1]
    assert interest.trans_date.year == 2026
    assert interest.trans_date.month == 8


def test_stops_at_interest_rate_chart_footer():
    result = parse_lines(SAMPLE_LINES, statement_year=2026)
    descriptions = [t.description for t in result.transactions]
    assert not any("PURCHASE" in d for d in descriptions)


def test_unrecognized_line_before_footer_is_warned_not_dropped_silently():
    lines = SAMPLE_LINES[:-4] + ["SOME UNEXPECTED FORMAT NOT MATCHING ANY RULE"]
    result = parse_lines(lines, statement_year=2026)
    assert any("Unrecognized line" in w for w in result.warnings)
