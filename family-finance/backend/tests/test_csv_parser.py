"""CSV parser tests — all data fabricated, mirroring column layouts only."""

from datetime import date

from app.parsers.csv_statement import parse_csv_statement


def _parse(text: str, forced_flip: bool | None = None):
    return parse_csv_statement(text.encode("utf-8"), forced_flip=forced_flip)


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


HEADERLESS_BANK_CSV = """2026-08-05,E-TRANSFER 000000000000 sample@example.com,,400.00
2026-08-04,PAY PER USE OVERDRAFT FEE,5.00,
2026-08-04,PREAUTHORIZED DEBIT SAMPLE INSURANCE,135.68,
2026-08-04,PREAUTHORIZED DEBIT SAMPLE MTG PYT,800.00,
"""


def test_headerless_bank_export():
    """CIBC-style exports have no header row — columns are inferred."""
    result = _parse(HEADERLESS_BANK_CSV)
    assert len(result.transactions) == 4
    assert result.warnings == []


def test_headerless_debit_positive_credit_negative():
    result = _parse(HEADERLESS_BANK_CSV)
    etransfer = next(t for t in result.transactions if "E-TRANSFER" in t.description)
    fee = next(t for t in result.transactions if "OVERDRAFT" in t.description)
    assert etransfer.amount == -400.00  # credit column = money in
    assert fee.amount == 5.00  # debit column = money out


def test_headerless_single_amount_column():
    result = _parse("2026-07-01,COFFEE PLACE,4.50\n2026-07-02,REFUND,(2.00)\n")
    assert len(result.transactions) == 2
    assert result.transactions[0].amount == 4.50
    assert result.transactions[1].amount == -2.00


# --- single Amount column, ledger sign convention (Simplii-style chequing) ---
#
# Many debit/chequing exports sign a single Amount column the opposite way
# from this app: a withdrawal (money out) is negative, a deposit (money in)
# is positive. There's no header text that says so — "Amount" doesn't
# distinguish the two conventions — so the parser leans on the fact that in
# any real statement, spending transactions vastly outnumber deposits: if
# most of the raw values come out negative, the file must be using the
# ledger convention, and every sign gets flipped so spending reads positive
# here too, matching the credit-card-style convention the rest of the app
# assumes.

SIMPLII_STYLE_CSV = """Date,Description,Amount
2026-07-02,SAMPLE GROCER,-84.20
2026-07-03,SAMPLE COFFEE,-6.75
2026-07-05,SAMPLE GAS BAR,-52.00
2026-07-14,PAYROLL DEPOSIT SAMPLE CORP,2140.00
2026-07-20,SAMPLE PHARMACY,-31.10
"""


def test_debit_account_ledger_convention_is_detected_and_flipped():
    result = _parse(SIMPLII_STYLE_CSV)
    grocer = next(t for t in result.transactions if "GROCER" in t.description)
    payroll = next(t for t in result.transactions if "PAYROLL" in t.description)
    # Spending was negative in the file; it must read positive (money out)
    # here, and the deposit must read negative (money in) — the app's
    # convention, opposite of what the file itself used.
    assert grocer.amount == 84.20
    assert payroll.amount == -2140.00


def test_flip_is_disclosed_as_a_warning_not_applied_silently():
    result = _parse(SIMPLII_STYLE_CSV)
    assert any("opposite sign convention" in w for w in result.warnings)


def test_a_tied_or_positive_majority_amount_column_is_left_alone():
    # Credit-card-style exports: charges positive (the app's own convention
    # already), refunds rare enough to never outnumber charges. Must NOT be
    # flipped, or a correctly-signed file would come out backwards.
    csv_text = """Date,Description,Amount
2026-07-01,SAMPLE RESTAURANT,45.00
2026-07-02,SAMPLE SHOP,60.00
2026-07-03,SAMPLE REFUND,-12.00
"""
    result = _parse(csv_text)
    restaurant = next(t for t in result.transactions if "RESTAURANT" in t.description)
    refund = next(t for t in result.transactions if "REFUND" in t.description)
    assert restaurant.amount == 45.00
    assert refund.amount == -12.00
    assert not any("opposite sign convention" in w for w in result.warnings)


def test_headerless_debit_convention_is_also_detected():
    """The same ledger-vs-app-convention ambiguity applies whether or not
    the file has a header row."""
    result = _parse(
        "2026-07-02,SAMPLE GROCER,-84.20\n"
        "2026-07-05,SAMPLE GAS BAR,-52.00\n"
        "2026-07-14,PAYROLL DEPOSIT,2140.00\n"
    )
    grocer = next(t for t in result.transactions if "GROCER" in t.description)
    assert grocer.amount == 84.20


# --- forced_flip: an account's remembered convention overrides the guess ---
#
# The majority-vote heuristic can misjudge a period with relatively few
# debits or an unusually deposit-heavy month — it re-guesses from scratch
# on every file, with no memory of what the account's statements actually
# use. Once an account's convention is known, a caller can force it
# instead of trusting the heuristic's per-file guess.


def test_flip_decision_is_reported_on_the_result():
    result = _parse(SIMPLII_STYLE_CSV)
    assert result.flip_amount_sign_applied is True

    result = _parse(
        "Date,Description,Amount\n2026-07-01,SAMPLE RESTAURANT,45.00\n"
    )
    assert result.flip_amount_sign_applied is False


def test_two_column_and_pdf_style_files_report_no_flip_decision():
    result = _parse(LEDGER_CSV)  # funds out / funds in columns, no single Amount column
    assert result.flip_amount_sign_applied is None


def test_forced_flip_true_overrides_a_heuristic_that_would_say_no():
    """A deposit-heavy period where deposits aren't a strict minority: the
    heuristic alone would leave it unflipped, reproducing the sign bug —
    forcing the account's established convention corrects it anyway."""
    csv_text = """Date,Description,Amount
2026-07-01,SAMPLE WITHDRAWAL,-40.00
2026-07-02,SAMPLE DEPOSIT,500.00
"""
    unforced = _parse(csv_text)
    assert unforced.flip_amount_sign_applied is False  # tie -> heuristic leaves it alone

    forced = _parse(csv_text, forced_flip=True)
    withdrawal = next(t for t in forced.transactions if "WITHDRAWAL" in t.description)
    assert withdrawal.amount == 40.00  # flipped to money-out despite the tie
    assert forced.flip_amount_sign_applied is True


def test_forced_flip_false_overrides_a_heuristic_that_would_say_yes():
    forced = _parse(SIMPLII_STYLE_CSV, forced_flip=False)
    grocer = next(t for t in forced.transactions if "GROCER" in t.description)
    assert grocer.amount == -84.20  # left exactly as the file had it
    assert forced.flip_amount_sign_applied is False


def test_forced_flip_uses_a_different_warning_than_the_guess():
    forced = _parse(SIMPLII_STYLE_CSV, forced_flip=True)
    assert any("established convention" in w for w in forced.warnings)
    assert not any("looked like it uses" in w for w in forced.warnings)
