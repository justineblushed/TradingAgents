from datetime import date

from pydantic import BaseModel


class ParsedTransaction(BaseModel):
    trans_date: date
    post_date: date | None = None
    description: str
    amount: float
    foreign_currency_note: str = ""
    suggested_category: str | None = None


class StatementPreview(BaseModel):
    account_last_four: str = ""
    transactions: list[ParsedTransaction]
    warnings: list[str] = []


class ImportRequest(BaseModel):
    account_id: int
    period_label: str = ""
    transactions: list[ParsedTransaction]


class TransactionOut(BaseModel):
    id: int
    trans_date: date
    post_date: date | None
    description: str
    amount: float
    category: str | None = None

    class Config:
        from_attributes = True


class CategoryOut(BaseModel):
    id: int
    name: str
    is_income: bool = False
    keywords: list[str] = []

    class Config:
        from_attributes = True


class CategoryCreate(BaseModel):
    name: str
    is_income: bool = False


class CategoryKeywordsUpdate(BaseModel):
    keywords: list[str]


class AccountCreate(BaseModel):
    name: str
    institution: str = ""
    account_type: str = "other"
    last_four: str = ""


class AccountOut(AccountCreate):
    id: int

    class Config:
        from_attributes = True


class DashboardSummary(BaseModel):
    """MVP scope is credit-card-only: 'credits' are payments/refunds against
    the card, not household income. True income tracking arrives once
    chequing/income accounts are added in Phase 2."""

    month: str
    total_charges: float
    total_credits: float
    net_change: float
    by_category: dict[str, float]
