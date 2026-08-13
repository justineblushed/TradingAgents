from dataclasses import dataclass, field
from datetime import date


@dataclass
class RawTransaction:
    trans_date: date
    post_date: date | None
    description: str
    amount: float
    foreign_currency_note: str = ""
    # Category name carried by the source itself (e.g. a CSV "Category"
    # column) — used as the suggestion when it matches a known category.
    category_hint: str = ""


@dataclass
class ParseResult:
    account_last_four: str = ""
    transactions: list[RawTransaction] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # Whether a single-amount-column CSV's signs were flipped to match this
    # app's convention. None when there was no such decision to make (a
    # PDF, or a CSV with separate debit/credit columns) — only ever set for
    # the single "Amount" column case, so callers can persist the decision
    # per account and skip re-guessing on the account's next import.
    flip_amount_sign_applied: bool | None = None
